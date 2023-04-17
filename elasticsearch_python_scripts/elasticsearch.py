import json
import requests
import datetime as dt
import pandas as pd
from wst.infra.hosts.services import service_address

def elasticsearch(d1,d2,filepath,message,host):
    HEADERS = {
        'Content-Type': 'application/json'
    }
    
    svc = service_address('elk/elasticsearch')
    uri = f'http://{svc[0]}:{svc[1]}/_search'
    
    query = json.dumps(
    {
        "size": 5000,
        "sort": [
        {
          "@timestamp": {
            "order": "desc",
            "unmapped_type": "boolean"
              }
            }
          ],
        "query": {
          "bool": {
            "must": [
                {
                    "match_phrase": {
                        "beat.hostname": host
                    }
                },
                {
                  "match_phrase": {
                    "message": message
                  }
                },
            ],
            "filter": [
                {
                  "match_phrase": {
                    "log.file.path": filepath
                  }
                },
                {
                  "range": {
                    "@timestamp": {
                      "gte": d1,
                      "lte": d2,
                      "format": "strict_date_optional_time"
                    }
                  }
                }
              ],
            "should": [],
            "must_not": []
            }
        }
        }
    )
    r = requests.get(uri, headers=HEADERS, data=query).json()
    li = []
    for line in r.get('hits').get('hits'):
        li.append(line)
        print(line['_source']['message'])
    return li

if _name_ == "_main_":
    #user input in utc
    d1="2022-10-10T21:04:39.221Z"
    d2="2022-10-13T16:50:57.430Z"
    hostname=""
    message=f"'command'"
    filepath=""
    t1 = elasticsearch(d1,d2,filepath,message,hostname)