# -*- coding: utf-8 -*-
import time,pytz
from datetime import datetime, timedelta
# from botocore.vendored import requests
import requests
import json
import re
import os
import boto3
import argparse
#from datetime import datetime
import vars as mvars

MAXIDELTIME = 300
REQ_TIMEOUT = (30,30)

session = requests.Session()
session.auth = (mvars.JENKINS_USR, mvars.JENKINS_PASS)

parser = argparse.ArgumentParser(description='ASG manager and monitor')
parser.add_argument('-t','--task', help='Task for the script (asg_manager, builds2elk, queue2elk)', required=True)
args = vars(parser.parse_args())

def get_queue(jenkinssrv):
  try:
    resp = session.get('{}/queue/api/json'.format(jenkinssrv), timeout=REQ_TIMEOUT)
  except requests.exceptions.RequestException as e:
    return None
  queueInfo = resp.json()
  jobs = []
  for j in queueInfo['items']:
    if len(re.findall('BuildableItem$', j['_class']))>0:
      QueueDuration = int(time.time() * 1000 - j['inQueueSince'])/1000
      jobs.append({'url': j['url'], 'why': j['why'], 'queue_duration': QueueDuration})
    else:
      continue
  return jobs

def get_required_labels(queue_items, allowed_labels):
  required_labels = dict()
  # Initialise the dict with 0
  for l in allowed_labels:
    required_labels[l] = 0

  required_labels['others'] = 0

  for q in queue_items:
    why = q['why'].encode("ascii", errors="ignore").decode()

    # "why": "‘Jenkins’ doesn’t have label ‘docker_client’"       -> Jenkins doesnt have label docker_client
    # "why": "There are no nodes with the label ‘docker_client’"  -> There are no nodes with the label docker_client
    # "why": "Waiting for next available executor on ‘i-07eeb97539dfb0b01’"
    # "why": "‘i-0a71b33d713a3b357’ is offline" - such nodes will be removed by the script
    if why.find('Jenkins doesnt have label') != -1 or why.find('There are no nodes with the label') != -1 :
      rlabel = why.split()[-1].strip()
      if rlabel in allowed_labels:
        required_labels[rlabel] +=1
      else:
        required_labels['others'] +=1

    elif why.find("Waiting for next available executor on") != -1 :
      # Get labels list of the node, check if the given label in the list
      node = why.split()[-1].strip()
      if node[0:2].lower() == 'i-':
        # Instance name !!! count only ALLOWED_LABELS !!!
        node_info = get_computer(node)
      	if not node_info is None:
          flag = 0
          for l in node_info['assignedLabels']:
            if l['name'] in allowed_labels:
              required_labels[l['name']] +=1
              flag += 1
          if flag == 0:
          # If no required labels were found in the node's labels
            required_labels['others'] +=1
        else:
          print("Label starts from i- we cannot distinguish it from instance name")
      elif node in allowed_labels:
        required_labels[node] +=1
      else:
        required_labels['others'] +=1

  num_labels = 0
  for l in required_labels:
    num_labels += required_labels[l]
  if num_labels != len(queue_items):
    print("Sum of required_labels doesn't match with number of items in the queue")

  return required_labels

def delete_node(nodeName):
  try:
    resp = session.post("{}/computer/{}/doDelete".format(mvars.JENKINS_SERVER, nodeName), timeout=REQ_TIMEOUT)
    if resp.status_code == requests.codes.ok:
      return True
  except requests.exceptions.RequestException as e:
    print ("Http Error:",e)

  return None

def get_computer(nodeName):
  resp = session.get("{}/computer/{}/api/json".format(mvars.JENKINS_SERVER,nodeName), timeout=REQ_TIMEOUT)
  if resp.status_code == requests.codes.ok:
    return resp.json()

  return None
# TODO: Should terminate slaves properly (remove labels, terminate instance, remove agent ...)
def toggle_computer_offline(nodeName):
  try:
    resp = session.post("{}/computer/{}/toggleOffline?offlineMessage=Taken_down".format(mvars.JENKINS_SERVER,nodeName), timeout=REQ_TIMEOUT)
    if resp.status_code == requests.codes.ok:
      return True
  except requests.exceptions.RequestException as e:
    print ("Http Error:",e)

  return None

def get_ec2_tag(ec2, InstanceId, tagKey):
  try:
    node_awsinfo = ec2.describe_instances(InstanceIds=[InstanceId])
    node_tags = node_awsinfo['Reservations'][0]['Instances'][0]['Tags']
    for tag in node_tags:
      if tag['Key'] == tagKey :
        return tag['Value']
  except e:
    return None

def postToELK(elkURL, index, Json):

    resp = requests.post('{}/{}/_doc/'.format(elkURL.rstrip('/'), index), json=Json)
    if not (200 <= resp.status_code < 300) :
        print("postToELK ERROR: "+resp.text)
    # print(resp.text)


def makeInfoFlat(info, preffix, info1):
    """
    We need to have flat array to be able to store/index it in ELK efectevly
    Flat dict is returned in info1
    """

    preffix = preffix.replace("LinuxBuild for ", "").replace("WindowsBuild for ", "").strip()

    for i in info:
        # cpreffix = '{}[{}]'.format(preffix, i)
        cpreffix = '{}[{}]'.format(preffix, i) if len(preffix)>0 else '{}'.format(i)
        if isinstance(info[i], (dict, list, set)):
            makeInfoFlat(info[i], cpreffix, info1)
        else:
            info1[cpreffix] = info[i]

def getBuildInfo(url, session, ExpandBuildsInProcess = True):
    """
    Returns given build info
    If ExpandBuildsInProcess = True then process all build
    if it false then only finished builds
    """
    try:
        resp = session.get('{url}/api/json?depth=2'.format(url = url.rstrip('/')), timeout=REQ_TIMEOUT)
    except requests.exceptions.RequestException as e:
        print ("Http Error:",e)
        return []

    buildInfo = resp.json()

    # list fields to return
    BUILDFIELDS = ("_class",
                    "building",
                    "duration",
                    "estimatedDuration",
                    "fullDisplayName",
                    "id",
                    "number",
                    "result",
                    "timestamp",
                    "url",
                  )

    filteredInfo = { key: buildInfo[key] for key in BUILDFIELDS }
    for item in buildInfo['actions']:
        if '_class' in item and item["_class"] == "jenkins.metrics.impl.TimeInQueueAction":
            filteredInfo['TimeInQueueAction'] = item
        elif '_class' in item and item["_class"] == "hudson.plugins.git.util.BuildData":
            if len( re.findall('PR-', item["lastBuiltRevision"]["branch"][0]["name"]) )>0 :
                filteredInfo['CommitSHA1'] = item["lastBuiltRevision"]["branch"][0]["SHA1"]

    # Flatten the array
    buildInfo = {}
    makeInfoFlat(filteredInfo, '', buildInfo)

    if not ExpandBuildsInProcess:
        if not buildInfo["building"]:
            # the build is finished we can get info about stages
            wfapi = []
            try:
                resp = session.get('{url}/wfapi'.format(url = url.rstrip('/')), timeout=REQ_TIMEOUT)
            except requests.exceptions.RequestException as e:
                print('Broken build {error} {url}/wfapi'.format(url = url.rstrip('/'), error = e))

            if resp.status_code == requests.codes.ok :
                wfapi = resp.json()

                for stage in wfapi["stages"]:
                    for nf in ("status","startTimeMillis","durationMillis","pauseDurationMillis"):
                        nfname = '{}[{}]'.format(stage["name"], nf).replace("LinuxBuild for ", "").replace("WindowsBuild for ", "").strip("'").strip()

                        buildInfo[nfname] = stage[nf]

    return buildInfo

def lastProcessedBuild(elkURL, index, buildUrl):
    """
    Returns last build processed with the system on previouse runs
    """
    SearchJson = {
            "from" : 0,
            "size" : 1,
            "_source": {
                "includes": [ "number" ]
            },
            "sort" : [
                {"number" : {"order" : "desc"}}
            ],
            "query": {
                "match_phrase": {
                    "url": {
                        "query": "{}*".format(buildUrl)
                    }
                }
            }
        }

    try:
        resp = requests.get('{}/{}/_search/'.format(elkURL.rstrip('/'), index), json=SearchJson)
        print(resp.text)
        rjson = json.loads(resp.text)
        print( rjson["hits"]["hits"][0]["_source"]["number"] )
        return rjson["hits"]["hits"][0]["_source"]["number"]
        # return 0
    except Exception as e:
        return 0


def getBuilds(joburl, session):
    """
    Get list of all builds by jobs url
    Supports: job.WorkflowJob, multibranch.WorkflowMultiBranchProject
    """
    url = '{url}/api/json'.format(url = joburl)
    try:
        resp = session.get(url, timeout=REQ_TIMEOUT)
    except requests.exceptions.RequestException as e:
        print ("Http Error:",e)
        return []

    jobinfo = resp.json()

    if jobinfo['_class'] == 'org.jenkinsci.plugins.workflow.job.WorkflowJob' :
        # Workflow job has builds
        return jobinfo['builds']

    elif jobinfo['_class'] == 'org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject' :
        # Multibranch job - need to iterate throgh all the branches to get all builds
        builds={}
        for branchjob in jobinfo['jobs']:
            # branch jobs of multibranch are Workflow jobs so do recursion call to process them
            # builds.append(branchjob['url']: getBuilds(branchjob['url'], session))
            builds[branchjob['url']] = getBuilds(branchjob['url'], session)
        return builds

    exit("Not supported Job class")

if __name__ == "__main__":

  if args['task'] == "asg_manager":

    queue = get_queue(mvars.JENKINS_SERVER)

    required_labels = get_required_labels(queue, [mvars.JENKINS_LABEL_LIN_ONDEMAND, mvars.JENKINS_LABEL_WIN_ONDEMAND])

    cw = boto3.client('cloudwatch',
                        region_name=mvars.CLUSTER_REGION,
                        aws_access_key_id=mvars.ACCESS_KEY,
                        aws_secret_access_key=mvars.SECRET_KEY)
    print("Required labels: ", required_labels)
    for label in required_labels:
      if label == mvars.JENKINS_LABEL_LIN_ONDEMAND:
        metric_name=mvars.JENKINS_QUEUE_METRIC_LIN_ONDEMAND
      elif label == mvars.JENKINS_LABEL_WIN_ONDEMAND:
        metric_name=mvars.JENKINS_QUEUE_METRIC_WIN_ONDEMAND
      else:
        metric_name=mvars.JENKINS_QUEUE_METRIC_OTHERS_REQUIRED_LABELS

      resp = cw.put_metric_data( MetricData=[{ 'MetricName': metric_name,
                                  'Dimensions': [{'Name': 'JobsInQueue','Value': 'JOBS'},],
                                  'Unit': 'Count','Value': required_labels[label] },], Namespace='BuildEnv/Jenkins')

    asg = boto3.client('autoscaling',
                        region_name=mvars.CLUSTER_REGION,
                        aws_access_key_id=mvars.ACCESS_KEY,
                        aws_secret_access_key=mvars.SECRET_KEY)
    ec2 = boto3.client('ec2',
                        region_name=mvars.CLUSTER_REGION,
                        aws_access_key_id=mvars.ACCESS_KEY,
                        aws_secret_access_key=mvars.SECRET_KEY)

    ec2res = boto3.resource('ec2',region_name=mvars.CLUSTER_REGION,
                                  aws_access_key_id=mvars.ACCESS_KEY,
                                  aws_secret_access_key=mvars.SECRET_KEY)

    for asg_name in [mvars.JENKINS_SLAVES_ASG_LIN_ONDEMAND, mvars.JENKINS_SLAVES_ASG_WIN_ONDEMAND]:
      # Iterating throw ASG and terminate unneeded resourses
      response = asg.describe_auto_scaling_groups(AutoScalingGroupNames = [asg_name])
      isWin = True if asg_name.lower().find("windows")>-1 else False
      for node in response['AutoScalingGroups'][0]['Instances']:
  #i-005ee52f9c62e9dd4
  #i-0e025c7c4c0f9
  #0123456789012345678
        jInstName = node['InstanceId'].upper()[0:15] if isWin else node['InstanceId']
        node_JenkinsInfo = get_computer(jInstName)

        #  Not_registred_in_Jenkins
        if node_JenkinsInfo is None:
        # If the agent was not able to connect/died
          instance = ec2res.Instance(node['InstanceId'])
          if (pytz.utc.localize(datetime.now())-instance.launch_time).total_seconds() >= 2*MAXIDELTIME :
            node_IdleSince = get_ec2_tag(ec2, node['InstanceId'], 'IdleSince')
            if node_IdleSince is not None :
              if int(time.time())-int(node_IdleSince) >= 3*MAXIDELTIME :
                print("Doesn't run/dead agent: ", node['InstanceId'],instance.launch_time,datetime.now())
                response = asg.terminate_instance_in_auto_scaling_group( InstanceId=node['InstanceId'], ShouldDecrementDesiredCapacity=True)
            else:
              # Set Idle tag if instance exist
              response = ec2.create_tags(Resources=[node['InstanceId']], Tags=[{'Key': 'IdleSince', 'Value': str(int(time.time()))}])

        #            IDLE
        elif node_JenkinsInfo['idle']:
          # check for termination
          response = asg.set_instance_protection(InstanceIds=[node['InstanceId']], AutoScalingGroupName=asg_name, ProtectedFromScaleIn=False)
          node_IdleSince = get_ec2_tag(ec2, node['InstanceId'], 'IdleSince')
          if node_IdleSince is not None :
            if int(time.time())-int(node_IdleSince) >= MAXIDELTIME :
              if not node_JenkinsInfo['offline'] :
                toggle_computer_offline(jInstName)
                # delete_node(jInstName)
              else:
                response = asg.terminate_instance_in_auto_scaling_group( InstanceId=node['InstanceId'], ShouldDecrementDesiredCapacity=True)
          else:
            # Set Idle tag if instance exist
            response = ec2.create_tags(Resources=[node['InstanceId']], Tags=[{'Key': 'IdleSince', 'Value': str(int(time.time()))}])
        elif not node_JenkinsInfo['idle']:
          response = asg.set_instance_protection(InstanceIds=[node['InstanceId']], AutoScalingGroupName=asg_name, ProtectedFromScaleIn=True)
          response = ec2.delete_tags(Resources=[node['InstanceId']], Tags=[{'Key': 'IdleSince'}])
          if node_JenkinsInfo['offline'] :
            toggle_computer_offline(jInstName)
            print("Make node online again", jInstName)

        else:
          print("!!! ERROR !!!", node['InstanceId'], jInstName, node_JenkinsInfo)

  # Post required_labels to ELK
  elif args['task'] == "queue2elk":

    queue = get_queue(mvars.JENKINS_SERVER)
    required_labels = get_required_labels(queue, [mvars.JENKINS_LABEL_LIN_ONDEMAND, mvars.JENKINS_LABEL_WIN_ONDEMAND])

    required_labels['jenkins_url'] = mvars.JENKINS_SERVER
    required_labels['timestamp'] = int(datetime.now().strftime("%s"))
    print(required_labels)
    postToELK(mvars.ELK_URL, mvars.ELK_JENKINS_QUEUE_INDEX, required_labels)
    # resp = requests.post('{}/{}/_doc/'.format(mvars.ELK_URL.rstrip('/'), mvars.ELK_QUEUE_INDEX), json=required_labels)
    # if not (200 <= resp.status_code < 300) :
    #     print("queue2elk ERROR: "+resp.text)

  elif args['task'] == "builds2elk":
    builds = getBuilds(mvars.JENKINS_SERVER + mvars.JENKINS_JOB, session)
    processed_jobs = 0
    for branch in builds:
      lastProcessed = lastProcessedBuild(mvars.ELK_URL, mvars.ELK_JENKINS_BUILDS_INDEX, branch)
      bbuilds = list(filter(lambda k: k['number'] > lastProcessed, builds[branch]))
      print('branch: {} last processed: {} BuildsToProcess: {}'.format(branch, lastProcessed, len(bbuilds)))
      if len(bbuilds) > 0 :
        bbuilds = sorted(bbuilds, key=lambda k: k['number'])
        for build in bbuilds:
          processed_jobs += 1
          # get build info out of Jenkins API
          buildInfo = getBuildInfo(build['url'], session, False)
          buildInfo['jenkins_url'] = mvars.JENKINS_SERVER.replace('http://', '').replace('https://', '').replace('/', '')
          buildInfo['jenkins_job'] = mvars.JENKINS_JOB
          # print(buildInfo)
          postToELK(mvars.ELK_URL, mvars.ELK_JENKINS_BUILDS_INDEX, buildInfo)
          # exit()postToELK(mvars.ELK_URL, mvars.ELK_QUEUE_INDEX, required_labels):
    print("Number of processed jobs: {}".format(processed_jobs))


  elif args['task'] == "asgsize2elk":

    cw = boto3.client('cloudwatch',
                    region_name=mvars.CLUSTER_REGION,
                    aws_access_key_id=mvars.ACCESS_KEY,
                    aws_secret_access_key=mvars.SECRET_KEY)

    # asg_info = []

    for g in [mvars.JENKINS_SLAVES_ASG_LIN_ONDEMAND, mvars.JENKINS_SLAVES_ASG_WIN_ONDEMAND]:
      response = cw.get_metric_statistics(
        Namespace='AWS/AutoScaling',
        MetricName='GroupTotalInstances',
        Dimensions=[{'Name': 'AutoScalingGroupName', 'Value': g}],
        StartTime=datetime.utcnow() - timedelta( minutes=5 ),
        EndTime=datetime.utcnow(),
        Period=60,
        Statistics=['Maximum']
      )

      # print(response)
      for d in response['Datapoints']:
        dpoint=dict()
        dpoint['timestamp'] = int((d['Timestamp']- datetime(1970, 1, 1, tzinfo= pytz.utc)).total_seconds())
        dpoint['asg_name'] = g
        dpoint['jenkins_url'] = mvars.JENKINS_SERVER
        dpoint['asg_size'] = d['Maximum']
        # print(dpoint)
        # asg_info.append(dpoint)
        postToELK(mvars.ELK_URL, mvars.ELK_ASG_INFO_INDEX, dpoint)


    # print(asg_info)
    # postToELK(mvars.ELK_URL, mvars.ELK_ASG_INFO_INDEX, asg_info)
