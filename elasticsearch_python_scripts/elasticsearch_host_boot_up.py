import argparse
from calendar import timegm
import datetime as dt
import json
import logging
import pandas as pd
import re
import requests
import time
logger = logging.getLogger(_name_)


def print_histogram(start_time, bootup_diff):
    """Plot Histogram"""
    start_boot = [(timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")), float(b)) for (s, b) in zip(start_time, bootup_diff)]
    plot_histogram([b for (_, b) in start_boot], n_bins=5)


def diff_host_boot_up(req_start, req_end):
    """

    Gives difference between start time and end time

    Args:
        req_start (int): wmp/elastic host request time
        req_end   (int): nginx/local start time on host

    Returns:
        int: difference between req_end and req_start in minutes
    """
    host_start_time = pd.to_datetime(req_start)
    nginx_start_time = pd.to_datetime(req_end)
    host_startup_time = nginx_start_time - host_start_time

    return int(host_startup_time.total_seconds() / 60)


def format_datetime(d):
    """Function to format time as YYYY-MM-DDTHH:MN:SEC.000Z"""
    d = d.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return d


def extract_wmp_elastic_host(es_res):
    """

    Stores wmp elastic hosts and their startup time in a Dict

    Args:
        es_res (list): stores elastic search result

    Returns:
        dict: hostname as key and request time as value
    """
    j = 0
    wmp_host_time = {}
    for i in range(len(es_res)):
        x = re.search(r"Starting elastic instances:", es_res[i]['_source']['message'])
        host_name = es_res[i]['_source']['message'][x.end() + 2:len(es_res[i]['_source']['message']) - 1]

        if "," in host_name:
            x1 = host_name.split(',')
            for k in range(len(x1)):
                x2 = x1[k][0:len(x1[k]) - 5].replace("<HostInstance:", "")

                if(x2 in wmp_host_time):
                    wmp_host_time[x2 + "*" + str(j)] = es_res[i]['_source']['@timestamp']
                    j += 1
                else:
                    wmp_host_time[x2] = es_res[i]['_source']['@timestamp']
        else:
            x2 = host_name[0:len(host_name) - 5].replace("<HostInstance:", "")
            if(x2 in wmp_host_time):
                wmp_host_time[x2 + "*" + str(j)] = es_res[i]['_source']['@timestamp']
                j += 1
            else:
                wmp_host_time[x2] = es_res[i]['_source']['@timestamp']

    return wmp_host_time


def host_boot_up(start_host):
    """

    Give details for  Hostname, starttime, endtime, hostname, message, time_diff

    Args:
        start_host (dict): wmp elastic hosts and their startup time in a Dictionary

    Returns:
        list: Hostname, starttime, endtime, hostname, message, time_diff

    """
    start_time = []
    end_time = []
    host_name = []
    message1 = []
    time_diff = []
    message = "NGINX is not running, starting it up"
    filepath = "/opt/services/nginx/local.log"
    for i in start_host:
        query_date_to_wmp = format_datetime(pd.to_datetime(start_host[i]) + pd.DateOffset(minutes=30))
        hostname = i if ("" not in i) else i[:i.find("")]
        scan_nginx = scan_es(start_host[i], query_date_to_wmp, filepath, message, hostname)
        if len(scan_nginx) == 0:
            continue
        else:
            start_time.append(start_host[i])
            end_time.append(scan_nginx[0]['_source']['@timestamp'])
            host_name.append(hostname)
            message1.append(scan_nginx[0]['_source']['message'])
            time_diff.append(diff_host_boot_up(start_host[i], scan_nginx[0]['_source']['@timestamp']))

    return start_time, end_time, host_name, message, time_diff


def scan_es(query_date_from, query_date_to, filepath, message, host):
    """
    Elasticsearch driver function

    Args:
        query_date_from  (string): start date for query
        query_date_to    (string): end date for query
        filepath         (string): log filepath
        message          (string): search message
        host             (string): hostname

    Returns:
        list: elasticsearch result
    """
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
            "stored_fields": [
                "*"
            ],
            "docvalue_fields": [
                {
                    "field": "@timestamp",
                    "format": "date_time"
                }
            ],
            "_source": {
                "excludes": []
            },
            "query": {
                "bool": {
                    "must": [
                        {
                            "match_phrase": {
                                "beat.hostname": host
                            }
                        },
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": query_date_from,
                                    "lte": query_date_to,
                                    "format": "strict_date_optional_time"
                                }
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
                            "match_phrase": {
                                "message": message
                            }
                        },
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": query_date_from,
                                    "lte": query_date_to,
                                    "format": "strict_date_optional_time"
                                }
                            }
                        },
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

    return li


def main():
    """
    Inputs for script

    Args:
        days (int): Get host_startup_time for last X days by default it will use 7

    """
    p = argparse.ArgumentParser(description='Host Startup time for last X days')
    p.add_argument('--days', type=int, default=7, help='last X days')
    args = p.parse_args()
    now = dt.datetime.now()
    query_date_from = format_datetime(now - dt.timedelta(days=args.days))
    query_date_to = format_datetime(now)
    domain = ConfigEnv().domain
    wmp_message = "Starting elastic instances"
    svc_name = f'wmp/elastic-{domain}'
    svc = service_address(svc_name)
    if not svc:
        svc_name = 'wmp/elastic'
        svc = service_address(svc_name)
    hostname = svc[0].replace("", "")
    wmp_filepath = f'/opt/services/{svc_name}.log'

    es_result = scan_es(query_date_from, query_date_to, wmp_filepath, wmp_message, hostname)
    wmp_host_list = extract_wmp_elastic_host(es_result)
    wmp_start_time, wmp_end_time, wmp_host_name, wmp_message, wmp_time_diff = host_boot_up(wmp_host_list)
    wmp_host_stats = pd.DataFrame({'Start time': wmp_start_time, 'End time': wmp_end_time,
                                   'hostname': wmp_host_name, 'message': wmp_message, 'Boot up time': wmp_time_diff})
    if(len(wmp_host_stats) == 0):
        logger.info('No Host Launched by the %s service', svc_name)
    else:
        # We use the below statement to filter the machine where startuptime is incorrect
        wmp_host_stats = wmp_host_stats[~(wmp_host_stats['Boot up time'] > 3 * (wmp_host_stats['Boot up time'].mean()))]
        logger.info('Host Launched by the %s service', svc_name)
        print(wmp_host_stats)
        print_histogram(wmp_host_stats['Start time'], wmp_host_stats['Boot up time'])
        download_data(wmp_host_stats, '.csv', 'elastic_wmp_host_stats.csv')


if _name_ == "_main_":
    init_logging()
    main()