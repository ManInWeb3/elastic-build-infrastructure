# AWS build infrastructure
This repo include all parts of the AWS build environment.

**CloudFormation folder**: all needed cloud formation templates to spawn the environment. You can use deployDEV.sh deployPROD.sh  scripts to deploy environemnt manually, in this case you have to provide correct values for all parameters.

**NFSServer and SMBServer folders**: docker files and scripts to build NFS and SAMBA server, used to share ccache and references between linux and windows slaves. I couldn't make ccache working with EFS, when I was working on this project, due to ccache trys to manage its cache properly so needs to be able to define size of the shared disk, EFS returns too big value of available size and ccache errors on this step and I couldn't find a workaround. 

**Packer**:  Hashicorp packer templates to build AMIs for windows and linux slaves. Navico sdk docker images have a pretty big size (up to 20Gb) so to decrease time to start a compilation and network traffic we pull all needed images into these AMIs. We have to keep list of pulled images synchronised with what we're using(it's better to generate the list automatically based on AppTargets.json) and regenerate AMIs every time we changed images (that is why Jenkins job includes these steps)
**asg_manager**: python script to check Jenkins master queue size and manage number of desired slaves.

## Limitations

1. Currently PROD and DEV environments have only one set of EBS volumes (jenkins home and ccache) per environemnt, so ***you can deploy only 1 DEV and 1 PROD environments at a time***. 
2. After DEV environment (not master branch of the repo) is deployed, the pipeline will wait pressed  REMOVE (or ABORT) button and discard the environment, but the environment will be removed in any case in 3 hours(configured in Jenkinsfile).
3. Build job takes windows and linux slaves docker containers tags as parameters (Current latest approved tags are set as default values).


