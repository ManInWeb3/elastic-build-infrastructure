set -e

echo "You shouldn't update the stack with this script, use Jenkins job instead!!!"
echo "And you will need to update the commands in the file from ../Jenkinsfile!!!"
exit

StackName=PRODJenkinsBuildEnvironment

echo "Deploying $StackName"
aws cloudformation package \
  --template-file CF_BuildEnvStack.yaml \
  --force-upload \
  --s3-bucket cf-templates-9uyh15oy0kly-us-east-1 \
  --output-template-file tmp-packaged-template.yaml

# exit
aws cloudformation deploy \
  --template-file tmp-packaged-template.yaml \
  --stack-name $StackName \
  --fail-on-empty-changeset \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
                JenkinsMasterIP=10.33.1.188 \
                KeyName=BuildInfrastructure \
                MasterHomeVolume=vol-019f16a51e11444f8 \
                CCACHEVolume=vol-09acdf8406f6d19f9 \
                LinAmiId=ami-0bcdfaf4af9665224 \
                WinAmiId=ami-0a841b6f9edb9e985 \
                JenkinsLinSlaveDockerTag=master-v0.1-136-ge7464e9 \
                JenkinsWinSlaveDockerTag=aws-qt560-qt5122 \
  --tags \
               'cc:project=Infrastructure R+D' \
               'cc:segment=SHARE' \
               'info:devPOC=vladimir.shevelev@navico.com' \
               'info:opsPOC=seth.bacon@navico.com' \
               'info:busPOC=tom.edvardsen@navico.com' \
               'cc:environment=PROD' \
               'env:buildsystem=RND'


