"""Fictional feed responses shaped like each provider's public job-board API."""

GREENHOUSE = {
    "jobs": [
        {
            "id": 4012345,
            "title": "Senior Backend Engineer",
            "updated_at": "2026-10-01T09:00:00-04:00",
            "first_published": "2026-09-28T09:00:00-04:00",
            "location": {"name": "Remote - UK"},
            "absolute_url": "https://boards.greenhouse.io/examplecorp/jobs/4012345",
            "content": "&lt;p&gt;We build &lt;strong&gt;payments&lt;/strong&gt;.&lt;/p&gt;&lt;h3&gt;Requirements&lt;/h3&gt;"
                       "&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;li&gt;PostgreSQL&lt;/li&gt;&lt;/ul&gt;"
                       "&lt;script&gt;alert(1)&lt;/script&gt;",
            "pay_input_ranges": [{"min_cents": 8000000, "max_cents": 9500000, "currency_type": "GBP",
                                  "title": "UK"}],
        },
        {"id": 4012346, "title": "Office Manager", "location": {"name": "London"},
         "absolute_url": "https://boards.greenhouse.io/examplecorp/jobs/4012346",
         "content": "&lt;p&gt;Run our London office.&lt;/p&gt;"},
        {"id": 4012347, "title": "No URL job", "content": "&lt;p&gt;x&lt;/p&gt;"},  # skipped: no link
    ],
    "meta": {"total": 3},
}

LEVER = [
    {
        "id": "7d1c2b3a-0000-4000-8000-000000000001",
        "text": "Platform Engineer",
        "hostedUrl": "https://jobs.lever.co/examplelabs/7d1c2b3a-0000-4000-8000-000000000001",
        "applyUrl": "https://jobs.lever.co/examplelabs/7d1c2b3a-0000-4000-8000-000000000001/apply",
        "createdAt": 1759300000000,
        "categories": {"location": "Berlin", "commitment": "Full-time", "team": "Infrastructure"},
        "workplaceType": "hybrid",
        "descriptionPlain": "Help us scale our platform.",
        "lists": [{"text": "What you'll need", "content": "<li>Kubernetes</li><li>Go</li>"}],
        "additionalPlain": "Visa sponsorship available.",
        "salaryRange": {"min": 70000, "max": 90000, "currency": "EUR", "interval": "per-year-salary"},
    },
    {"id": "7d1c2b3a-0000-4000-8000-000000000002", "text": "Contract Designer",
     "hostedUrl": "https://jobs.lever.co/examplelabs/7d1c2b3a-0000-4000-8000-000000000002",
     "categories": {"commitment": "Contractor"}, "workplaceType": "unspecified",
     "descriptionPlain": "Design things for six months."},
]

ASHBY = {
    "apiVersion": "1",
    "jobs": [
        {
            "id": "b2a1c3d4-0000-4000-8000-0000000000aa",
            "title": "Data Engineer",
            "location": "New York",
            "employmentType": "FullTime",
            "isListed": True,
            "isRemote": True,
            "publishedAt": "2026-10-05T12:00:00.000Z",
            "jobUrl": "https://jobs.ashbyhq.com/exampleco/b2a1c3d4-0000-4000-8000-0000000000aa",
            "descriptionHtml": "<p>Build pipelines with <b>Airflow</b> and SQL.</p>",
            "descriptionPlain": "Build pipelines with Airflow and SQL.",
            "compensation": {"summaryComponents": [
                {"compensationType": "Equity"},
                {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD",
                 "minValue": 150000, "maxValue": 180000},
            ]},
        },
        {"id": "hidden", "title": "Unlisted role", "isListed": False,
         "jobUrl": "https://jobs.ashbyhq.com/exampleco/hidden", "descriptionPlain": "Secret."},
    ],
}
