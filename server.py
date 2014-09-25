from __future__ import print_function

from flask import Flask, request
from flask import g # 'g' is Flask's magic 'stuff' storer http://flask.pocoo.org/docs/0.10/api/#flask.g

import random
import redis
import json
import os


REDIS_DATABASE = 0
START_DEPTH = 1

app = Flask(__name__)
redis_pool = redis.ConnectionPool(
    host=os.environ["REDIS_PORT_6379_TCP_ADDR"], 
    port=os.environ["REDIS_PORT_6379_TCP_PORT"],
    db=REDIS_DATABASE)


def log(msg):
    print("- %s" % msg)


# Web routes


@app.route("/")
def home():
    return "Up and running!,"


@app.route("/", methods=["POST"])
def start_crawl():
    urls = request.data.split("\n")  # GOTCHA: Might not scale well for large URL lists
    
    # Make a new job_id
    job_id = g.db.incr('NEXT_JOB_ID')

    # Write job data to database
    # TODO: Execute in a transaction (?)
    for url in urls:
        to_queue = "%s$%s$%s" % (job_id, START_DEPTH, url)
        log("Push to CRAWL_QUEUE: %s" % to_queue)
        g.db.rpush('CRAWL_QUEUE', to_queue) # Enqueue

    return json.dumps({"job_id":job_id})


@app.route("/status/<int:job_id>/")
def get_status(job_id):
    return json.dumps({
            "completed": g.db.get('JOB_%s_COMPLETED' % job_id) or 0,
            "inprogress": g.db.get('JOB_%s_INPROGRESS' % job_id) or 0
        })


@app.route("/results/<int:job_id>/")
def get_results(job_id):
    return json.dumps({
            "images": list(g.db.smembers("JOB_%s_RESULTS" % job_id))  # All elements
            #g.db.lrange("JOB_%s_RESULTS",0,-1) # All elements
        }, indent=4, separators=(',', ': '))


@app.route("/queue/")
def get_queue():
    return json.dumps({
            "queue": g.db.lrange("CRAWL_QUEUE",0,-1), # All elements
            "queue_len":g.db.llen("CRAWL_QUEUE"),
        })


# Database handling

def connect_db():
    #return redis.StrictRedis(host='localhost', port=6379, db=0)
    return redis.StrictRedis(connection_pool=redis_pool)

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    # db = getattr(g, 'db', None)
    # if db is not None:
    #     db.close()
    pass


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=80)
