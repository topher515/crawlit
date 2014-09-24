from flask import Flask, request
from flask import g # 'g' is Flask's magic 'stuff' storer http://flask.pocoo.org/docs/0.10/api/#flask.g

import random
import redis
import json

app = Flask(__name__)


# Web routes

@app.route("/", methods=["POST"])
def start_crawl():
    urls = request.data.split("\n")  # GOTCHA: Might not scale well for large URL lists
    
    # Make a new job_id
    job_id = g.db.incr('NEXT_JOB_ID')

    # Write job data to database
    # TODO: Execute in a transaction (?)
    for url in urls:
        g.db.rpush('CRAWL_QUEUE', "%s$%s$%s" % (job_id, depth, url)) # Enqueue

    return "%s" % job_id


@app.route("/status/<int:job_id>/")
def get_status():
    return json.dumps({
            "completed": g.db.get('JOB_%s_COMPLETED') or 0,
            "inprogress": g.db.get('JOB_%s_INPROGRESS') or 0
        })


@app.route("/result/<int:job_id>/")
def get_result():
    return json.dumps({
            "images":g.db.lrange("JOB_%s_RESULTS",0,-1) # All elements
        })



if __name__ == "__main__":
    app.run(debug=True)