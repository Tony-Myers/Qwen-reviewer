# Tests

`test_extraction.py` guards the table extraction against the regression that
prompted it: the coefficient tables of a journal article were invisible to the
pipeline, because pdfplumber's default strategy needs ruled lines in both
directions and most journal tables are set booktabs-style with horizontal
rules only.

It needs the paper it was written against:

    cd ~/local-llm/qwen35-review
    cp /path/to/Myers_et_al_2020_swimming.pdf tests/paper.pdf
    .venv/bin/python tests/test_extraction.py

To check a different paper, point `PDF` at it and update the page numbers and
the expected values near the top. The useful checks to keep are: the results
tables are found, no narrative page is mistaken for a table, and the
coefficients survive intact rather than being split across cells.
