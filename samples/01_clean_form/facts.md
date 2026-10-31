# Fact list — 01 clean form (hand-written before generation)

1. Client: Bright Smile Dental (fictional).
2. The clinic lost about 18 appointment slots per week to no-shows.
3. Reception phoned every patient the day before; this took around two hours a day.
4. The team built a small web tool ranking next-day appointments by no-show chance.
5. Reception now calls only the 15 highest-risk patients each afternoon.
6. Two reception staff were trained to use it.
7. A gradient boosting model was trained on 14 months of anonymised appointment history.
8. Features: booking lead time, past no-shows, appointment type.
9. The model is retrained every Sunday night.
10. Tools: Python, scikit-learn, pandas, FastAPI, PostgreSQL.
11. Challenge: duplicate records from an old booking system migration.
12. Challenge: patient names had to be removed before data left the clinic.
13. Result: over the first 8 weeks, weekly no-shows fell from about 18 to 11.
14. Result: daily reminder calls dropped from around two hours to 40 minutes.

Not stated (must not appear): revenue, cost savings, % improvement, number of patients, clinic size.
