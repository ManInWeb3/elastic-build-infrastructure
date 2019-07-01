#!/bin/bash
#set -euxo

# 2017-05-11 22:53:20   OR 2017-05-11
AFTERTIME="2019-06-09 00:00"
TMPFILE=$(mktemp)
REPFILE=$(mktemp)
#echo $TMPFILE
#STRING2SEARCH='IOException'
#STRING2SEARCH='Failed to run image|ERROR: Timeout after 180 seconds'
#STRING2SEARCH='port 22: Connection timed out|The remote end hung up unexpectedly|Unable to Checkout'
#STRING2SEARCH='requests.exceptions.SSLError:|requests.exceptions.ConnectionError'
#STRING2SEARCH='error MSB6006: "CL.exe" exited with code -1'
#STRING2SEARCH='error MSB6006: "CL.exe" exited|File "clcache.py", line'
STRING2SEARCH='AbortException docker login failed'
#STRING2SEARCH='compiler is out of heap space'
#STRING2SEARCH='Access is denied:.*stats\.txt\.new'
#STRING2SEARCH='Unable to Merge PR-'
#|ConnectTimeoutException: Connect to bitbucket.navico.com'


#LOGDIRS="/results/docker/volumes/jenkins_home/_data/jobs/ /results/jenkins-builds/"
LOGDIRS="/results/docker/volumes/jenkins_home/_data/jobs/NOS_multibranch/"
for ddir in $LOGDIRS; do
        find "$ddir" -type f -newermt "$AFTERTIME" -name "log" | \
        xargs -d '\n' grep -l -E "$STRING2SEARCH"| \
        while read fname; do
#       stat $fname
                dt=$(stat -c "%y" "$fname"|awk '{print($1)}')
                ln=$(grep -n -E "$STRING2SEARCH" "$fname"|head -1|awk 'BEGIN{FS=":"}{print($1)}'|grep -oE "^([0-9])*")
                tm=$(tail -n +"$(($ln - 1))" "$fname"|head -n 10|grep -Em1 "^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}"|awk '{print($1)}')
                if [ "${tm}x" = "x" ]; then
                        tm="logmodifytime:$(stat -c '%y' "$fname"|awk '{print($2)}')"
                fi
#       echo "$dt - $ln - $tm"
                echo "$dt $tm $fname" >> $TMPFILE
        done
done
cat $TMPFILE | sort >> $REPFILE

echo -e '---------------------------------------------\n' >> $REPFILE

cat $TMPFILE |awk '{print($1)}' |sort | uniq -c >> $REPFILE

echo "Failed builds after $AFTERTIME"
cat $REPFILE

# messagt=$(< $REPFILE)

# url='https://hooks.slack.com/services/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'             # example: https://hooks.slack.com/services/QW3R7Y/D34DC0D3/BCADFGabcDEF123
# username='THOR'

# to="#monitoring"
# subject="\'$STRING2SEARCH\' in build logs for the lst 7 days"
# emoji=':frowning:'
# message="${subject}:\n ${message}"

# # Build our JSON payload and send it as a POST request to the Slack incoming web-hook URL
# payload="payload={\"channel\": \"${to//\"/\\\"}\", \"username\": \"${username//\"/\\\"}\", \"text\": \"${message//\"/\\\"}\", \"icon_emoji\": \"${emoji}\"}"
# echo $payload
# curl -m 5 --data-urlencode "${payload}" $url

rm -f $TMPFILE $REPFILE $TIMEFILE
