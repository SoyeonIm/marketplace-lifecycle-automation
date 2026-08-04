# Architecture and ownership

## Logical production flow

```mermaid
flowchart TB
    subgraph Collection["Collection and identity"]
      E["Web and app events"] --> S["Segment / GA4"]
      S --> W["Snowflake raw schemas"]
      C["Consent and preference centre"] --> W
    end
    subgraph Modelling["Analytics engineering"]
      W --> D["dbt staging"]
      D --> M["Member 360 and campaign marts"]
      M --> Q["Tests, freshness and lineage"]
    end
    subgraph Activation["Customer data and Martech"]
      M --> H["Hightouch audience sync"]
      H --> B["Braze Canvas"]
      B --> X["Email, push and in-app"]
    end
    subgraph Measurement["Campaign analytics"]
      X --> R["Response and conversion events"]
      R --> W
      M --> A["Experiment and ROI analysis"]
      A --> P["Power BI / decision report"]
    end
```

## Ownership boundaries

- The analyst owns the semantic definition of eligibility and outcomes.
- Analytics engineering owns reliable transformation and deployment patterns.
- Lifecycle owns the journey and member experience.
- Platform teams own source collection and destination availability.
- Legal and Privacy approve policy; automated tests enforce only the encoded portion of that policy.

The project keeps these boundaries explicit so a successful notebook cannot silently become an
unsafe production audience.

