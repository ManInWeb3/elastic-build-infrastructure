#!/bin/bash
#set -euxo pipefail
. ../env_names

CCACHEVOLUME=ccache
REFVOLUME=references
CCISCREATED=$(docker volume inspect $CCACHEVOLUME &>/dev/null;echo $?)
REFISCREATED=$(docker volume inspect $REFVOLUME &>/dev/null;echo $?)

if [ $CCISCREATED -eq 1 ]; then
        echo "Please create ccache volume \'docker volume create --name $CCACHEVOLUME\'"
        echo "And put ccache.conf to that volume \'docker run --rm -v `pwd`:/src -v $CCACHEVOLUME:/data $REGISTRY/${TAGNFS} cp /src/ccache.conf /data/ccache.conf\'"
        exit
fi

if [ $REFISCREATED -eq 1 ]; then
        echo "Please create REFERENCES volume \'docker volume create --name $REFVOLUME\'"
        echo "And put the references folder into it"
        exit
fi

## environment variables
# You will need to provide at the following 3 environment variables to configure the nfs exports:
# * NFS_EXPORT_DIR_1
# * NFS_EXPORT_DOMAIN_1
# * NFS_EXPORT_OPTIONS_1
# -> NFS_EXPORT_DIR_1 NFS_EXPORT_DOMAIN_1(NFS_EXPORT_OPTIONS_1)
## to start

docker run -d --privileged --restart=always \
        -v $CCACHEVOLUME:/ccache \
        -e NFS_EXPORT_DIR_1=/ccache \
        -e NFS_EXPORT_DOMAIN_1=\* \
        -e NFS_EXPORT_OPTIONS_1=rw,insecure,no_subtree_check,no_root_squash,fsid=1 \
        -p 111:111 -p 111:111/udp \
        -p 2049:2049 -p 2049:2049/udp \
        -p 32765:32765 -p 32765:32765/udp \
        -p 32766:32766 -p 32766:32766/udp \
        -p 32767:32767 -p 32767:32767/udp \
        $REGISTRY/${TAGNFS}


#       -v $REFVOLUME:/references \
#       -e NFS_EXPORT_DIR_2=/references \
#       -e NFS_EXPORT_DOMAIN_2=\* \
#       -e NFS_EXPORT_OPTIONS_1=rw,insecure,no_subtree_check,no_root_squash,fsid=1 \



