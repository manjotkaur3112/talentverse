from . import insights, interview, jobs, learning, profiles, projects, readiness


def register(app):
    for module in (profiles, jobs, readiness, learning, interview, projects, insights):
        app.register_blueprint(module.bp)
