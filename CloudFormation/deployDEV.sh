set -e

StackName=DEVJenkinsBuildEnvDEV

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
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
                KeyName=BuildInfrastructure \
                MasterHomeVolume=vol-0bd4b2406dc1ec04c \
                CCACHEVolume=vol-09e7d77bdb1fde8c1 \
                LinAmiId=ami-0b9c25e5e249714a1 \
                WinAmiId=ami-094c1b0d2501a358c \
                JenkinsLinSlaveDockerTag=aws-dev \
                JenkinsWinSlaveDockerTag=aws-dev-qt560-qt5122 \
  --tags \
               'cc:project=Infrastructure R+D' \
               'cc:segment=SHARE' \
               'info:devPOC=vladimir.shevelev@navico.com' \
               'info:opsPOC=seth.bacon@navico.com' \
               'info:busPOC=tom.edvardsen@navico.com' \
               'cc:environment=DEV' \
               'env:buildsystem=RND'


  # --fail-on-empty-changeset \


                # JenkinsMasterIP=10.33.1.199 \
