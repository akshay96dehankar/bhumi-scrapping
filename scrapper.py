
import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

URL = "https://mahabhunakasha.mahabhumi.gov.in/27/index.html"

OUTPUT_FILE = Path(__file__).with_name("location_data_updated.json")

STATE_ID = "level_0"
CATEGORY_ID = "level_1"
DISTRICT_ID = "level_2"
TALUKA_ID = "level_3"
VILLAGE_ID = "level_4"
PLOT_ID = "surveyNumber"

ESTIMATED_VILLAGES = 44000

driver = webdriver.Chrome()
wait = WebDriverWait(driver, 25)

start_time = time.time()
processed_villages = 0
total_plot_entries = 0


# --------------------------------------------------
# JSON INITIALIZATION
# --------------------------------------------------

if OUTPUT_FILE.exists():
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as file:
            location_data = json.load(file)

        if not isinstance(location_data, dict):
            location_data = {}

    except (json.JSONDecodeError, OSError):
        location_data = {}
else:
    location_data = {}

location_data.setdefault("Maharastra", {})
location_data["Maharastra"].setdefault("Rural", {})
location_data["Maharastra"].setdefault("Urban", {})


def save_json():
    """Save the collected data using UTF-8 and preserve Marathi text."""

    temporary_file = OUTPUT_FILE.with_suffix(".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(
            location_data,
            file,
            ensure_ascii=False,
            indent=4,
        )

    temporary_file.replace(OUTPUT_FILE)


# --------------------------------------------------
# DROPDOWN HELPERS
# --------------------------------------------------

def wait_for_ajax():
    """Wait for jQuery AJAX requests, if the website uses jQuery."""

    try:
        wait.until(
            lambda d: d.execute_script(
                "return typeof jQuery === 'undefined' || jQuery.active === 0"
            )
        )
    except TimeoutException:
        pass

    # Allow dependent dropdowns to refresh.
    time.sleep(0.7)


def is_placeholder(value, text):
    """Identify dropdown placeholder entries."""

    value = (value or "").strip()
    text = (text or "").strip()

    if not value or not text:
        return True

    value_lower = value.lower()
    text_lower = text.lower()

    if "select" in value_lower or "select" in text_lower:
        return True

    if value in ("----", "---", "--"):
        return True

    if text in ("----", "---", "--"):
        return True

    return False


def get_options(element_id):
    """
    Return dropdown entries as (value, visible_text).

    The visible text is preserved for JSON keys.
    """

    for attempt in range(4):
        try:
            element = wait.until(
                EC.presence_of_element_located(
                    (By.ID, element_id)
                )
            )

            dropdown = Select(element)
            options = []

            for option in dropdown.options:
                value = option.get_attribute("value")
                text = option.text

                if is_placeholder(value, text):
                    continue

                # Preserve the displayed name while removing
                # surrounding whitespace.
                options.append(
                    (value.strip(), text.strip())
                )

            return options

        except StaleElementReferenceException:
            time.sleep(0.5)

    raise Exception(
        f"Could not read dropdown: {element_id}"
    )


def get_plot_numbers():
    """
    Return exact visible plot-number strings.

    Does not convert plot numbers to integers.
    Therefore values such as 01, 73/A and 73/B
    remain strings.
    """

    for attempt in range(4):
        try:
            element = wait.until(
                EC.presence_of_element_located(
                    (By.ID, PLOT_ID)
                )
            )

            dropdown = Select(element)
            plot_numbers = []

            for option in dropdown.options:
                value = option.get_attribute("value") or ""
                text = option.text

                if is_placeholder(value, text):
                    continue

                # Use the exact displayed plot number.
                # Do not use the option's value attribute.
                plot_numbers.append(text)

            return plot_numbers

        except StaleElementReferenceException:
            time.sleep(0.5)

    raise Exception("Could not read plot-number dropdown.")


def select_option(element_id, value):
    """Select an entry and wait for dependent data to load."""

    for attempt in range(4):
        try:
            element = wait.until(
                EC.element_to_be_clickable(
                    (By.ID, element_id)
                )
            )

            Select(element).select_by_value(value)

            wait_for_ajax()
            return

        except StaleElementReferenceException:
            time.sleep(0.5)

    raise Exception(
        f"Could not select {value!r} in {element_id}"
    )


# --------------------------------------------------
# PROGRESS DISPLAY
# --------------------------------------------------

def print_progress(
    category,
    district,
    taluka,
    village,
    village_plot_count,
):
    elapsed = time.time() - start_time

    percentage = min(
        processed_villages / ESTIMATED_VILLAGES * 100,
        100,
    )

    print(
        f"Progress: {percentage:.2f}% | "
        f"Villages: {processed_villages} | "
        f"Category: {category} | "
        f"District: {district} | "
        f"Taluka: {taluka} | "
        f"Village: {village} | "
        f"Village plots: {village_plot_count} | "
        f"Total plot entries: {total_plot_entries} | "
        f"Elapsed: {elapsed:.1f}s",
        flush=True,
    )


# --------------------------------------------------
# MAIN SCRAPER
# --------------------------------------------------

try:
    print("Opening Maharashtra BhuNakasha website...")

    driver.get(URL)

    wait.until(
        EC.presence_of_element_located(
            (By.ID, CATEGORY_ID)
        )
    )

    wait_for_ajax()

    print("Website loaded.")
    print("Output file:", OUTPUT_FILE)

    # The URL is already the Maharashtra BhuNakasha portal.
    # We do not require Maharashtra to appear in level_0.

    categories = get_options(CATEGORY_ID)

    if not categories:
        raise Exception(
            "No Rural/Urban categories found. "
            "Check whether the website loaded correctly."
        )

    print(
        "Categories found:",
        [text for _, text in categories],
    )

    # --------------------------------------------------
    # CATEGORY
    # --------------------------------------------------

    for category_value, category_name in categories:

        print(f"\nProcessing category: {category_name}")

        # Normalize only the category key.
        category_lower = category_name.strip().lower()

        if "rural" in category_lower:
            category_key = "Rural"
        elif "urban" in category_lower:
            category_key = "Urban"
        else:
            category_key = category_name.strip()

        location_data["Maharastra"].setdefault(
            category_key, {}
        )

        select_option(CATEGORY_ID, category_value)

        # --------------------------------------------------
        # DISTRICTS
        # --------------------------------------------------

        districts = get_options(DISTRICT_ID)

        for district_value, district_name in districts:

            print(f"\nDistrict: {district_name}")

            district_data = (
                location_data["Maharastra"][category_key]
                .setdefault(district_name, {})
            )

            select_option(DISTRICT_ID, district_value)

            # --------------------------------------------------
            # TALUKAS
            # --------------------------------------------------

            talukas = get_options(TALUKA_ID)

            for taluka_value, taluka_name in talukas:

                print(f"  Taluka: {taluka_name}")

                taluka_data = district_data.setdefault(
                    taluka_name, {}
                )

                select_option(TALUKA_ID, taluka_value)

                # --------------------------------------------------
                # VILLAGES
                # --------------------------------------------------

                villages = get_options(VILLAGE_ID)

                for village_value, village_name in villages:

                    select_option(VILLAGE_ID, village_value)

                    # --------------------------------------------------
                    # EXACT PLOT NUMBERS
                    # --------------------------------------------------

                    plot_numbers = get_plot_numbers()

                    # Use the exact displayed village name as key.
                    # Save plot numbers as strings.
                    taluka_data[village_name] = plot_numbers

                    processed_villages += 1
                    total_plot_entries += len(plot_numbers)

                    # Save after every village.
                    save_json()

                    print_progress(
                        category_key,
                        district_name,
                        taluka_name,
                        village_name,
                        len(plot_numbers),
                    )

    # --------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------

    save_json()

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("SCRAPING COMPLETED")
    print("=" * 60)
    print(f"Villages processed: {processed_villages}")
    print(f"Total plot entries: {total_plot_entries}")
    print(f"Elapsed time: {elapsed:.2f} seconds")
    print(f"JSON file: {OUTPUT_FILE}")
    print("=" * 60)

except KeyboardInterrupt:
    print("\nScraping stopped by user.")
    print("Saving collected data...")

    save_json()

    print(f"Villages processed: {processed_villages}")
    print(f"Plot entries counted this run: {total_plot_entries}")
    print(f"Saved file: {OUTPUT_FILE}")

except Exception as error:
    print("\nERROR:", error)

    try:
        save_json()
        print("Collected data saved to:", OUTPUT_FILE)
    except Exception as save_error:
        print("Could not save JSON:", save_error)

finally:
    driver.quit()
