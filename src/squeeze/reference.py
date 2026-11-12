"""Names for the codes published by the ABS."""

HOUSEHOLDS = {
    "P1": "Working households",
    "P2": "Age pensioners",
    "P3": "Other payment households",
    "P4": "Self-funded retirees",
    "PBLCI": "Pensioner benchmark",
}

HOUSEHOLD_DETAIL = {
    "P1": "Employee households",
    "P2": "Age pensioner households",
    "P3": "Other government transfer recipient households",
    "P4": "Self-funded retiree households",
    "PBLCI": "Pensioner and beneficiary households",
}

STATES = {
    "1": ("New South Wales", "Sydney"),
    "2": ("Victoria", "Melbourne"),
    "3": ("Queensland", "Brisbane"),
    "4": ("South Australia", "Adelaide"),
    "5": ("Western Australia", "Perth"),
    "6": ("Tasmania", "Hobart"),
    "7": ("Northern Territory", "Darwin"),
    "8": ("Australian Capital Territory", "Canberra"),
}

INDUSTRIES = {
    "B": "Mining",
    "C": "Manufacturing",
    "D": "Utilities",
    "E": "Construction",
    "F": "Wholesale",
    "G": "Retail",
    "H": "Hospitality",
    "I": "Transport",
    "J": "Media and telecom",
    "K": "Finance",
    "L": "Real estate services",
    "M": "Professional services",
    "N": "Admin and support",
    "O": "Public administration",
    "P": "Education",
    "Q": "Health and care",
    "R": "Arts and recreation",
    "S": "Other services",
}

COLOURS = {
    "P1": "#4CC9F0",
    "P2": "#F4A261",
    "P3": "#FF6B6B",
    "P4": "#C084FC",
    "PBLCI": "#90E0A8",
    "wages": "#3DDC97",
    "prices": "#FFD166",
    "mortgage": "#FF8C42",
    "behind": "#FF5D73",
}

# Words that do not belong on a page for a non-technical reader.
BANNED_DASHBOARD_WORDS = (
    "sqlmesh",
    "duckdb",
    "lakefs",
    "minio",
    "argo",
    "opentelemetry",
    "jaeger",
    "conformal",
    "statsforecast",
    "arima",
    "bronze",
    "silver",
    "gold layer",
    "schema",
    "pipeline",
    "backtest",
    "quantile",
    "residual",
    "seasonally",
    "sdmx",
    "docker",
    "kubernetes",
    "nowcast",
    "regression",
    "confidence interval",
    "warehouse",
    "audit",
)
