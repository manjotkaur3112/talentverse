"""Free learning resources. URLs are curated official docs or generated search links.
The AI is never asked for URLs, so nothing here can be hallucinated."""
from urllib.parse import quote_plus

from matcher import norm

CURATED = {
    "python": [("Official Python tutorial", "https://docs.python.org/3/tutorial/")],
    "javascript": [("javascript.info", "https://javascript.info/"),
                   ("MDN Learn web development", "https://developer.mozilla.org/en-US/docs/Learn_web_development")],
    "html": [("MDN Learn web development", "https://developer.mozilla.org/en-US/docs/Learn_web_development")],
    "css": [("MDN Learn web development", "https://developer.mozilla.org/en-US/docs/Learn_web_development")],
    "react": [("React official tutorial", "https://react.dev/learn")],
    "typescript": [("TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html")],
    "node.js": [("Node.js learn", "https://nodejs.org/en/learn")],
    "express": [("Express guide", "https://expressjs.com/en/starter/installing.html")],
    "flask": [("Flask tutorial", "https://flask.palletsprojects.com/en/stable/tutorial/")],
    "django": [("Django tutorial", "https://docs.djangoproject.com/en/stable/intro/tutorial01/")],
    "fastapi": [("FastAPI tutorial", "https://fastapi.tiangolo.com/tutorial/")],
    "sql": [("SQLBolt interactive lessons", "https://sqlbolt.com/")],
    "postgresql": [("PostgreSQL tutorial", "https://www.postgresql.org/docs/current/tutorial.html")],
    "mongodb": [("MongoDB University", "https://learn.mongodb.com/")],
    "git": [("Pro Git book", "https://git-scm.com/book/en/v2")],
    "docker": [("Docker get started", "https://docs.docker.com/get-started/")],
    "kubernetes": [("Kubernetes basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/")],
    "aws": [("AWS getting started", "https://aws.amazon.com/getting-started/")],
    "linux": [("Linux Journey", "https://linuxjourney.com/")],
    "java": [("dev.java learn", "https://dev.java/learn/")],
    "c++": [("learncpp.com", "https://www.learncpp.com/")],
    "pandas": [("10 minutes to pandas", "https://pandas.pydata.org/docs/user_guide/10min.html")],
    "numpy": [("NumPy absolute beginners", "https://numpy.org/doc/stable/user/absolute_beginners.html")],
    "scikit-learn": [("scikit-learn user guide", "https://scikit-learn.org/stable/user_guide.html")],
    "machine learning": [("Google Machine Learning Crash Course", "https://developers.google.com/machine-learning/crash-course")],
    "deep learning": [("fast.ai practical deep learning", "https://course.fast.ai/")],
    "pytorch": [("PyTorch tutorials", "https://pytorch.org/tutorials/")],
    "tensorflow": [("TensorFlow tutorials", "https://www.tensorflow.org/tutorials")],
    "nlp": [("Hugging Face NLP course", "https://huggingface.co/learn/nlp-course")],
    "statistics": [("Khan Academy statistics", "https://www.khanacademy.org/math/statistics-probability")],
    "rest api": [("REST API tutorial", "https://restfulapi.net/")],
    "tailwind": [("Tailwind CSS docs", "https://tailwindcss.com/docs")],
    "data structures": [("GeeksforGeeks DSA tutorial", "https://www.geeksforgeeks.org/learn-data-structures-and-algorithms-dsa-tutorial/")],
}


def resources_for(skill: str) -> list[dict]:
    """Curated links when known, plus two search links that always work."""
    out = [{"title": t, "url": u, "source": "curated"} for t, u in CURATED.get(norm(skill), [])]
    q = quote_plus(skill)
    out.append({"title": f"Free {skill} tutorials on YouTube", "source": "search",
                "url": f"https://www.youtube.com/results?search_query={q}+tutorial+for+beginners"})
    out.append({"title": f"freeCodeCamp articles about {skill}", "source": "search",
                "url": f"https://www.freecodecamp.org/news/search/?query={q}"})
    return out
