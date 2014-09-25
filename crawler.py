from __future__ import print_function

import redis
import json
import requests
import os

from bs4 import BeautifulSoup as bsoup
from urlparse import urljoin # 2.7
#from urllib.parse import urljoin # 3.x


REDIS_DATABASE = 0

r = redis.StrictRedis(
    host=os.environ["REDIS_PORT_6379_TCP_ADDR"], 
    port=os.environ["REDIS_PORT_6379_TCP_PORT"],
    db=REDIS_DATABASE)

# In order to receive notifications when the CRAWL_QUEUE tasks
# are enqueued, we must enable `notify-keyspace-events` on lists
# (http://redis.io/topics/notifications)
# HACK: Instead of setting the `notify-keyspace-events in the redis
# config we just do it whenever we start a crawler. This is sorta
# ghetto but doesn't really break anything
r.config_set("notify-keyspace-events","Kl")

def log(msg):
    print("- %s" % msg)
def warn(msg):
    print("-(warn) %s" % msg)


def do_crawl(job_id, depth, url):
    """
    Perform a new crawl task for the given `job_id` and `url`.

    If `depth > 0` then enqueue additional crawl tasks for each
    valid `<a href=""></a>` tag encountered at this URL.

    NOTE: This works purely on static HTML. No Javascript gets run!
    """

    log("Starting crawl (job_id='%s' depth='%s' url='%s')" % (
            job_id, depth, url))

    # Increment inprogress
    r.incr("JOB_%s_INPROGRESS" % job_id)

    try:
        # Get image urls
        page = requests.get(url).content

        html = bsoup(page)

        # Push all img srcs to database
        for img_tag in html.find_all('img'):
            if not img_tag.get("src"):
                # Skip images with empty src attrs
                continue 
            r.sadd("JOB_%s_RESULTS" % job_id, img_tag["src"])

        # If we should go deeper, enqueue more crawls 
        if depth > 0:
            for a_tag in html.find_all("a"):
                href = a_tag.get("href","")
                if not href or href.startswith("javascript"):
                    continue
                # Build full url
                full_url = urljoin(url, href)
                # Enqueue a crawl for this job for this url, decrementing depth counter
                r.rpush('CRAWL_QUEUE', "%s$%s$%s" % (job_id, depth - 1, full_url))
    
    except requests.exceptions.SSLError:
        warn("SSL Error: Skipping url '%s'")

    finally:
        # Always decrement inprogress
        r.decr("JOB_%s_INPROGRESS" % job_id)

    # Increment completed
    r.incr("JOB_%s_COMPLETED" % job_id)



def pop_next_crawl():
    """
    Pop the next crawl task from the crawl queue

    Return `job_id` and `url` for that crawl task
    """
    # Get next task on the crawl queue
    crawl_task = r.lpop("CRAWL_QUEUE")
    if not crawl_task:
        return

    job_id, depth, url = crawl_task.split("$", 2)
    return int(job_id), int(depth), url


def start_dequeueing():
    log("Start dequeueing...")
    while True:
        next_crawl = pop_next_crawl()
        if not next_crawl:
            break
        do_crawl(*next_crawl)


def run():
    # Dequeue all the crawl tasks available
    start_dequeueing()
    
    # Once we've dequeued all the crawl tasks, subscribe to
    # the crawl queue to watch for more tasks

    subscribe_channel = "__keyspace@%s__:CRAWL_QUEUE" % REDIS_DATABASE
    pubsub = r.pubsub()
    pubsub.subscribe([subscribe_channel])

    log("Begin subscribe...")

    for item in pubsub.listen():
        log("Got item: %s" % item)
        if item['type'] != 'message':
            continue
        log("Saw message: %s" % item)
        if item["data"] == 'rpush':
            start_dequeueing()




if __name__ == "__main__":
    run()
