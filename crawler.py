import redis
import json
from bs4 import BeautifulSoup as bsoup

REDIS_DATABASE = 0

r = redis.StrictRedis(host='localhost', port=6379, db=REDIS_DATABASE)


def do_crawl(job_id, depth, url):
    """
    Perform a new crawl task for the given `job_id` and `url`.

    If `depth > 0` then enqueue additional crawl tasks for each
    valid `<a href=""></a>` tag encountered at this URL.

    NOTE: This works purely on static HTML. No Javascript gets run!
    """

    # Increment inprogress
    r.incr("JOB_%S_INPROGRESS")

    try:
        # Get image urls
        page = requests.get(url)
        html = bsoup(page)

        # Push all img srcs to database
        for img_tag in html.find_all('img'):
            g.db.rpush("JOB_%s_RESULTS", img_tag["src"])

        # If we should go deeper, enqueue more crawls 
        if depth > 0:
            for a_tag in html.find_all("a"):
                # Enqueue a crawl for this job for this url, decrementing depth counter
                g.db.rpush('CRAWL_QUEUE', 
                    "%s$%s$%s" % (job_id, depth - 1, url))

    finally:
        # Always decrement inprogress
        r.decr("JOB_%S_INPROGRESS")

    # Increment completed
    r.incr("JOB_%S_COMPLETED")



def next_crawl():
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
    while True:
        next_crawl = get_next_crawl()
        if not next_crawl:
            break
        handle_crawl(*next_crawl)


def run():
    # Dequeue all the crawl tasks available
    start_dequeueing()
    
    # Once we've dequeued all the crawl tasks, subscribe to
    # the crawl queue to watch for more tasks
    def subcribe_handler(message):
        if message["data"] == 'rpush':
            start_dequeueing()
    subscribe_channel = "__keyspace@%s__:CRAWL_QUEUE rpush"
    p.subscribe(**{subscribe_channel: subscribe_handler})


