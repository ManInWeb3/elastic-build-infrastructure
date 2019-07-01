#!/bin/bash

set -euxo pipefail
. ../env_names

docker push $REGISTRY/${TAGSMB}
