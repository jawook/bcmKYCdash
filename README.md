# Class Poll Dashboard

A viewer-only Streamlit dashboard for exploring poll responses from class sessions. The KYC Checks tab supports the consistent multi-section CSV export stored in `Results/KYC/`.

## Run locally

1. Install Python 3.12.
2. Create and activate a virtual environment.
3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the dashboard:

   ```bash
   streamlit run app.py
   ```

The app will open in your browser and automatically combine the available KYC activity files.

## Add poll results

Place each KYC activity CSV export in the `Results/KYC/` folder and commit it to the repository. It will be included automatically, with no dashboard upload step or code change. Before publishing, confirm that files contain no personal or sensitive information you do not intend to make public.

```text
Results/
└── KYC/
    ├── activity-01.csv
    ├── activity-02.csv
    └── ...
```

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. In Streamlit Community Cloud, create an app from the repository.
3. Set the main file path to `app.py`.
4. Deploy. Streamlit Cloud will install packages from `requirements.txt`.

## Expected data

For the included KYC format, each question is followed by a CSV header beginning with `Response`. The parser adds `Activity` from the file's poll title and extracts `Target` from the text after the final colon in each question. Future activity types can use separate subfolders, parsing rules, and dashboard tabs.

## Development checks

Install `requirements-dev.txt`, then run:

```bash
pytest
ruff check .
```
