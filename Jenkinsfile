pipeline {
  // agent { label 'docker_client' }
  agent none
  options {
    buildDiscarder(logRotator(numToKeepStr: '10'))
    timestamps()
  }

  parameters {
    string(defaultValue: "master-v0.1-136-ge7464e9", description: 'Linux slaves docker tag docker-ubuntu-pipeline-agent:XXX', name: 'LinuxSlaveTag')
    string(defaultValue: "aws-qt560-qt5122", description: 'Windows slaves docker tag docker-navico-windows-sdk:XXX', name: 'WindowsSlaveTag')
  }

  environment {
    AWSCredentials = 'dc31d825-6dc1-42b2-9d07-52a2e7abfd91'
    ArtifactsCredentials = 'd7460232-28b3-48f9-a346-8399314d9526'
    DockerRegistry = 'artifacts.navico.com'
    CFTemplatesS3Bucket = 'cf-templates-9uyh15oy0kly-us-east-1'
    StackKeyName = 'BuildInfrastructure'
    AWSRegion = 'us-east-1'

    // Will be set after we built them
    LinuxSlavesAmiID = ''
    WindowsSlavesAmiID = ''
    // Will be set later based on branch and environment
    StackName = ''
    JenkinsMasterIPOverride =''
    MasterHomeVolume=''
    CCACHEVolume=''

    UserChoice = ''
  }

  stages {
    stage ('Set env vars') {
      steps {
        script {
          if (env.BRANCH_NAME == "master") {
            //  PROD
            EnvType = 'PROD'
            StackName = 'PRODJenkinsBuildEnvironment'
            JenkinsMasterIPOverride ='JenkinsMasterIP=10.33.1.188'
            MasterHomeVolume='vol-019f16a51e11444f8'
            CCACHEVolume='vol-09acdf8406f6d19f9'
          } else {
            // DEV inv
            EnvType = 'DEV'
            StackName = 'DEVJenkinsBuildEnvDEV'
            JenkinsMasterIPOverride =''
            // On dev branches we use dynamic IP
            MasterHomeVolume='vol-0bd4b2406dc1ec04c'
            CCACHEVolume='vol-09e7d77bdb1fde8c1'
          }
        } // script
      }
    } //stage

    stage ('Build AMI images') {
      parallel {
        stage ('Build Linux slaves AMI') {
          agent { label 'docker_client' }
          steps {
            checkout scm

            withCredentials([
              usernamePassword(credentialsId: AWSCredentials, usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY'),
              usernamePassword(credentialsId: ArtifactsCredentials, usernameVariable: 'ART_USER', passwordVariable: 'ART_PASS')
            ]) {
              // params.LinuxSlaveTag - Tag of docker-ubuntu-pipeline-agent to pull into the AMI
                dir('Packer'){
                  script {
                    sh label: "Packer build Linux slaves AMI", script:"""
                      packer build \\
                        -var LinuxSlaveTag=${params.LinuxSlaveTag} \\
                        -var DockerRegistry=${DockerRegistry} \\
                        -var DockerUser=\${ART_USER} \\
                        -var DockerPassword=\${ART_PASS} \\
                        LinuxSlavesAMI.json
                      cat LinuxSlavesAMI-manifest.json
                      """
                    def manifest = readJSON file: "LinuxSlavesAMI-manifest.json"
                    LinuxSlavesAmiID = manifest.builds[0].artifact_id.split(':').last()
                  } // script
              } // dir
            } // withcredentials
          } //steps
        } //stage

        stage ('Build Windows slaves AMI') {
          agent { label 'docker_client' }
          steps {
            checkout scm

            withCredentials([
              usernamePassword(credentialsId: AWSCredentials, usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY'),
              usernamePassword(credentialsId: ArtifactsCredentials, usernameVariable: 'ART_USER', passwordVariable: 'ART_PASS')
            ]) {
              // params.LinuxSlaveTag - Tag of docker-ubuntu-pipeline-agent to pull into the AMI
              dir('Packer'){
                script {
                  sh label: "Packer build Windows slaves AMI", script:"""
                    packer build \\
                      -var WindowsSlaveTag=${params.WindowsSlaveTag} \\
                      -var DockerRegistry=${DockerRegistry} \\
                      -var DockerUser=\${ART_USER} \\
                      -var DockerPassword=\${ART_PASS} \\
                      WindowsSlavesAMI.json
                    cat WindowsSlavesAMI-manifest.json
                    """
                  def manifest = readJSON file: "WindowsSlavesAMI-manifest.json"
                  WindowsSlavesAmiID = manifest.builds[0].artifact_id.split(':').last()
                } // script
              } // dir
            } // withcredentials
          } //steps
        } //stage
      }// parallel
    }

    stage ('Package and deploy stack') {
      agent { label 'docker_client' }
      steps {
        checkout scm

        withCredentials([ usernamePassword(credentialsId: AWSCredentials, usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY') ]) {
          withEnv(["AWS_DEFAULT_REGION=${AWSRegion}"]) {
            dir('CloudFormation'){
              script {
                sh label: "Package updated stack", script:"""
                  aws cloudformation package \
                    --template-file CF_BuildEnvStack.yaml \
                    --force-upload \
                    --s3-bucket ${CFTemplatesS3Bucket} \
                    --output-template-file tmp-packaged-template.yaml
                """

                sh label: "Deploy updated stack", script:"""
                  env
                  aws cloudformation deploy \
                    --template-file tmp-packaged-template.yaml \
                    --stack-name ${StackName} \
                    --capabilities CAPABILITY_NAMED_IAM \
                    --fail-on-empty-changeset \
                    --parameter-overrides ${JenkinsMasterIPOverride} \
                        KeyName=${StackKeyName} \
                        MasterHomeVolume=${MasterHomeVolume} \
                        CCACHEVolume=${CCACHEVolume} \
                        LinAmiId=${LinuxSlavesAmiID} \
                        WinAmiId=${WindowsSlavesAmiID} \
                        JenkinsLinSlaveDockerTag=${params.LinuxSlaveTag} \
                        JenkinsWinSlaveDockerTag=${params.WindowsSlaveTag} \
                    --tags \
                        'cc:project=Infrastructure R+D' \
                        'cc:segment=SHARE' \
                        'info:devPOC=edward.tew@navico.com' \
                        'info:opsPOC=seth.bacon@navico.com' \
                        'info:busPOC=tom.edvardsen@navico.com' \
                        'cc:environment=${EnvType}' \
                        'env:buildsystem=RND'
                """
              } // script
            } // dir
          } // withENV
        } // withcredentials
      } //steps
    } // stage

    stage ('If not master wait user input') {
      agent none
      steps {
        script {
          if (env.BRANCH_NAME != "master") {
            try {
              println "DEV environment: waiting for user's command to remove ${StackName} and AMIs, otherwise it will be removed in 3 hours."
              timeout(time: 360, unit: 'MINUTES') { // change to a convenient timeout for you
                  input message: "Click REMOVE to remove ${StackName} stack or it will be removed in 3 hours.\n Click Abort to leave the stack (you will have to remove it manually.)", ok: 'REMOVE'
              }

            } catch(err) { // timeout reached or input false
              def user = err.getCauses()[0].getUser()
              if('SYSTEM' == user.toString()) { // SYSTEM means timeout.
                  echo "Time is up, removing"
                  // no matter the input the build was successful
                  currentBuild.result = 'SUCCESS'
                  UserChoice = 'TIMEOUT'
              } else {
                  echo "Aborted by: [${user}]"
                  echo "All artifacts left, you need to remove them when you're ready."
                  // no matter the input the build was successful
                  currentBuild.result = 'SUCCESS'
                  UserChoice = 'ABORTED'
              }
            }
          } // If not master
        } //script
      } // steps
    } //stage

    // If not MASTER branch (DEV environment)
    // then give time to test the deployed environment and remove all the artifacts
    stage ('Cleaning up') {
      agent { label 'docker_client' }
      when {
        allOf {
          not { branch 'master' }
          expression { return UserChoice != 'ABORTED' }
          expression { return currentBuild.result != 'FAILURE' } // we leave failed builds to be able to analise what was wrong
       }
        beforeAgent true
      }
      steps {
        withCredentials([ usernamePassword(credentialsId: AWSCredentials, usernameVariable: 'AWS_ACCESS_KEY_ID', passwordVariable: 'AWS_SECRET_ACCESS_KEY') ]) {
          withEnv(["AWS_DEFAULT_REGION=${AWSRegion}"]) {

            script {
            // If we got error we need to investagate
              println "DEV environment: Cleaning Stack, AMIs and snapshots"
              try{
                sh label: "Delete ${StackName} stack", script:"""
                  aws cloudformation delete-stack --stack-name ${StackName} || echo "Cannot find ${StackName} stack"
                """
              } catch(Exception ex) {
                 println("Failed to remove stack ${StackName} with exception ${ex}");
              }

              [LinuxSlavesAmiID, WindowsSlavesAmiID].each { AMI ->
                try{
                  sh label: "Get AMI's snapshot id", script:"""
                    aws ec2 describe-images --image-ids ${AMI} > ${AMI}.json
                  """
                  ami_json = readJSON file: "${AMI}.json"
                  snap_id = ami_json.Images[0].BlockDeviceMappings[0].Ebs.SnapshotId
                  sh label: "Delete AMIs ${AMI} and snapshots ${snap_id}", script:"""
                    aws ec2 deregister-image --image-id ${AMI} || echo "Cannot find ${AMI}"
                    aws ec2 delete-snapshot --snapshot-id ${snap_id} || echo "Cannot find ${snap_id}"
                  """
                } catch(Exception ex) {
                   println("Failed to describe/remove AMI ${AMI} with exception ${ex}");
                }
              } //each

            } // script
          } //withENV
        } // withcredentials
      } //steps
    } // stage
  } //stages

}
