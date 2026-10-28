"""Create / update logic for profiles."""
from models import Education, Experience, Profile, Project, Skill, db


class NotFound(Exception):
    pass


def get_owned(owner_id: str, profile_id: int) -> Profile:
    p = Profile.query.filter_by(id=profile_id, owner_id=owner_id).first()
    if p is None:
        raise NotFound("Profile not found.")
    return p


def _merge_skills(p, items):
    existing = {s.name.lower(): s for s in p.skills}
    for s in items:
        cur = existing.get(s.name.lower())
        if cur is None:
            obj = Skill(name=s.name, category=s.category, proficiency=s.proficiency)
            p.skills.append(obj)
            existing[s.name.lower()] = obj
        else:
            if cur.category == "other" and s.category != "other":
                cur.category = s.category
            if s.proficiency:
                cur.proficiency = s.proficiency


def _merge_experience(p, items):
    key = lambda role, org: (role.lower(), (org or "").lower())
    existing = {key(e.role, e.organization): e for e in p.experiences}
    for e in items:
        cur = existing.get(key(e.role, e.organization))
        if cur is None:
            obj = Experience(role=e.role, organization=e.organization, start_date=e.start_date,
                             end_date=e.end_date, highlights=list(e.highlights))
            p.experiences.append(obj)
            existing[key(e.role, e.organization)] = obj
        else:
            cur.start_date = cur.start_date or e.start_date
            cur.end_date = cur.end_date or e.end_date
            have = list(cur.highlights or [])
            cur.highlights = have + [h for h in e.highlights if h not in have]  # reassign so JSON change is tracked


def _merge_education(p, items):
    key = lambda d, i: (d.lower(), (i or "").lower())
    existing = {key(e.degree, e.institution): e for e in p.education}
    for e in items:
        cur = existing.get(key(e.degree, e.institution))
        if cur is None:
            obj = Education(degree=e.degree, institution=e.institution, year=e.year)
            p.education.append(obj)
            existing[key(e.degree, e.institution)] = obj
        elif e.year:
            cur.year = e.year


def _merge_projects(p, items):
    existing = {x.title.lower(): x for x in p.projects}
    for x in items:
        cur = existing.get(x.title.lower())
        if cur is None:
            obj = Project(title=x.title, tech=list(x.tech), description=x.description)
            p.projects.append(obj)
            existing[x.title.lower()] = obj
        else:
            have = list(cur.tech or [])
            cur.tech = have + [t for t in x.tech if t.lower() not in {h.lower() for h in have}]
            if x.description:
                cur.description = x.description


def save_profile(owner_id, data, profile_id=None, mode="merge"):
    """Create a profile, or update an existing one by merging (default) or replacing it."""
    created = profile_id is None
    if created:
        p = Profile(owner_id=owner_id)
        db.session.add(p)
    else:
        p = get_owned(owner_id, profile_id)

    replace = created or mode == "replace"
    for field in ("full_name", "email", "summary"):
        value = getattr(data, field)
        if value is not None or replace:
            setattr(p, field, value)

    if replace and not created:
        p.skills.clear()
        p.experiences.clear()
        p.education.clear()
        p.projects.clear()
        db.session.flush()

    _merge_skills(p, data.skills)
    _merge_experience(p, data.experience)
    _merge_education(p, data.education)
    _merge_projects(p, data.projects)

    db.session.commit()
    return p, created
