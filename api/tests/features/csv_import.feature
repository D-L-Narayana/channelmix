Feature: CSV import with format detection
  Marketers upload the raw exports of their ad platforms; ChannelMix detects the format,
  previews the mapping and only writes on commit.

  Scenario: Google Ads export is detected and previewed
    Given a workspace
    When I dry-run import the "google_ads.csv" export
    Then the detected format is "google_ads" with channel "google"
    And the mapping uses "Cost" for spend and "Day" for day
    And the preview has 5 rows and nothing was written

  Scenario: Meta Ads Manager export is detected and committed
    Given a workspace
    When I import the "meta_ads.csv" export
    Then the detected format is "meta_ads" with channel "meta"
    And the mapping uses "Amount spent (INR)" for spend and "Link clicks" for clicks
    And 2 campaigns were created and 4 rows upserted
    And an "import.completed" event was emitted

  Scenario: Generic template with a channel column
    Given a workspace
    When I import the "generic.csv" export
    Then the detected format is "generic"
    And the channel-mix report for 2025-10-01 to 2025-10-02 lists channels "google, meta, other"

  Scenario: Re-importing the same file does not double count
    Given a workspace
    When I import the "google_ads.csv" export
    And I import the "google_ads.csv" export
    Then the total spend for 2025-10-01 to 2025-10-03 is 7434.56
