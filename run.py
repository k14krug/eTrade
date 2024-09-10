import os
from project import create_app

config_name = os.getenv('FLASK_CONFIG') or 'default'
app, celery = create_app()
app.app_context().push()

if __name__ == "__main__":
    app.run(port=5010, debug=True)

