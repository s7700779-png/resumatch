import logging, os
from flask import Flask, jsonify
from . import config, db, batches


def create_app(data_dir=None, recover=True):
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    config.set_data_dir(data_dir or os.getenv("RESUMATCH_DATA") or config.ROOT / "backend" / "data")
    db.init()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 600 * 1024 * 1024
    origins = config.cors_origins()
    try:
        from flask_cors import CORS
        CORS(app, resources={r"/api/*": {"origins": origins}})
    except ImportError:
        @app.after_request
        def cors(resp):
            from flask import request
            if request.headers.get("Origin") in origins:
                resp.headers["Access-Control-Allow-Origin"] = request.headers["Origin"]
                resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
                resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
            return resp
    from .api import bp
    app.register_blueprint(bp)

    def e(code, msg):
        return lambda _e: (jsonify(error=dict(code=str(code), message=msg)), code)
    app.register_error_handler(404, e(404, "Not found"))
    app.register_error_handler(405, e(405, "Method not allowed"))
    app.register_error_handler(413, e(413, "Upload too large"))

    @app.errorhandler(Exception)
    def unexpected(exc):
        logging.getLogger("resumatch").exception("unhandled error")
        return jsonify(error=dict(code="server_error", message="Something went wrong on the server.")), 500
    batches.reset_pool()
    if recover:
        batches.purge_older_than(db.get_settings()["retention_days"])
        batches.recover()
    return app
