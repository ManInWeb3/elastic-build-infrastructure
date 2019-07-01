#!/bin/bash

set -euxo pipefail
. ../env_names

docker build -t $REGISTRY/${TAGSMB} .

