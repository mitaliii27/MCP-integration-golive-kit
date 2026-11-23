# Discovery questionnaire

**Process & value**
1. Describe one recent real case from request to completion. Who touched it, in which systems, how long did each step wait?
2. How many such cases per week/month? What does one cost today (time, rework, delay)?
3. What does a wrong outcome cost, and who notices?

**Systems & data**
4. Which systems of record are involved? Which release/edition? Which APIs (REST/OData/other) are already exposed?
5. How is authentication done for service-to-service calls? Are there sandbox/test tenants with realistic data?
6. Which fields are mandatory vs derived? Any master-data quality problems?

**Risk & compliance**
7. Which actions need a human approval today, and at what thresholds?
8. Which data must never leave the system boundary or appear in a prompt/log?
9. Which regulations or internal policies apply (retention, audit, segregation of duties)?

**Model & hosting**
10. Which model providers/endpoints are approved? Any data-residency constraints?
11. Is there an existing observability/logging stack the agent must report into?

**Adoption**
12. Who are the first users? What would make them stop using it?
13. How will we know after 4 weeks live that it is working?
