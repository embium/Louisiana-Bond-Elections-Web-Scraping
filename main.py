import asyncio
import csv
from datetime import datetime
from playwright.async_api import async_playwright, Playwright
import re

url = "https://voterportal.sos.la.gov/graphical"
time_to_wait_between_clicks = 3
filename = "bonds_la.csv"

fields = [
    "Year",
    "Summary",
    "Question",
    "District",
    "votes_for",
    "percent_for",
    "votes_against",
    "percent_against",
    "result",
]

with open(filename, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(fields)


async def run(playwright: Playwright):
    firefox = playwright.firefox
    browser = await firefox.launch(headless=False)
    page = await browser.new_page()
    await page.goto(url)
    await asyncio.sleep(time_to_wait_between_clicks)
    elections_selector = "id=ElectionId"
    await page.wait_for_selector(elections_selector)
    elections_handle = await page.query_selector(elections_selector)
    count_elections = await elections_handle.evaluate("e => e.options")
    for index_election in count_elections:
        if index_election != "0":
            await elections_handle.select_option(index=int(index_election))
            await asyncio.sleep(time_to_wait_between_clicks)
        elections_selected_text = await elections_handle.evaluate(
            "el => el.options[el.selectedIndex].text"
        )
        elections_selected_date = datetime.strptime(
            elections_selected_text, "%a %b %d %Y"
        )
        elections_selected_year = elections_selected_date.year
        tabs_selector = ".nav-tabs"
        await page.wait_for_selector(tabs_selector)
        tabs_handle = await page.query_selector(tabs_selector)
        await tabs_handle.evaluate(
            """(function(){
tabs = document.querySelector('.nav-tabs').children
return [...tabs].filter(e => e.innerText === "Parish")[0].firstChild
})().click()
"""
        )
        await asyncio.sleep(time_to_wait_between_clicks)
        parishes_selector = ".parish-select"
        await page.wait_for_selector(parishes_selector)
        parishes_handle = await page.query_selector(parishes_selector)
        count_parishes = await parishes_handle.evaluate("e => e.options")
        for index_parish in range(len(count_parishes) - 1):
            await parishes_handle.select_option(index=int(index_parish))
            await page.get_by_text("View Results").click()
            await asyncio.sleep(time_to_wait_between_clicks)
            parish_header_selector = ".parish-header .ng-binding"
            await page.wait_for_selector(parish_header_selector)
            parish_header_handle = await page.query_selector(parish_header_selector)
            parish_header_text = await parish_header_handle.inner_text()
            races_selector = ".race-container:visible"
            await page.wait_for_selector(races_selector)
            races_locator = page.locator(
                races_selector,
            )
            races_count = await races_locator.count()
            runs_in_multiple_parishes_selector = (
                ".race-title [ng-show=showMultiparishText]"
            )
            runs_in_multiple_parishes_handle = await page.query_selector_all(
                runs_in_multiple_parishes_selector
            )
            choice_titles_selector = ".race-title-text"
            choice_titles_handle = await page.query_selector_all(choice_titles_selector)
            for choices_index in range(races_count):
                choices_locator = races_locator.nth(choices_index).locator(
                    ".choice-width-ref:visible"
                )
                if not choices_locator:
                    continue
                runs_in_multiple_parishes = await runs_in_multiple_parishes_handle[
                    choices_index
                ].is_visible()
                if runs_in_multiple_parishes:
                    continue
                choice_title_text = await choice_titles_handle[
                    choices_index
                ].inner_text()
                await choice_titles_handle[choices_index].click()
                choice_summary_selector = "id=TabFull"
                choice_summary_handle = await page.query_selector(
                    choice_summary_selector
                )
                if choice_summary_handle:
                    choice_summary_text = await choice_summary_handle.inner_text()
                    await page.get_by_text("Close").click()
                else:
                    choice_summary_text = choice_title_text
                choice_title_text = await choice_titles_handle[
                    choices_index
                ].inner_text()
                results_text = await races_locator.nth(choices_index).evaluate(
                    "e => e.innerText"
                )
                results_search = re.search(
                    "(\d,?\d+)\s+(Approved|Defeated)\s+(YES)\s+(\d+)%\s+(\d,?\d+)\s+(NO)\s+(\d+)%?",
                    results_text,
                )
                if results_search:
                    yes_votes_count = re.sub("[^\d\.]", "", results_search.group(1))
                    no_votes_count = re.sub("[^\d\.]", "", results_search.group(5))
                    yes_percentage = results_search.group(4)
                    no_percentage = results_search.group(7)
                    votes_outcome = (
                        "pass" if results_search.group(2) == "Approved" else "fail"
                    )
                    final_output = [
                        elections_selected_year,
                        choice_title_text,
                        choice_summary_text.strip(),
                        parish_header_text,
                        yes_votes_count,
                        no_votes_count,
                        yes_percentage,
                        no_percentage,
                        votes_outcome,
                    ]
                    with open(filename, "a", newline="") as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(final_output)

            await page.get_by_text("change parish").click()


async def main():
    async with async_playwright() as playwright:
        await run(playwright)


asyncio.run(main())
