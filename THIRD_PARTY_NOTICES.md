# Third-Party Notices

## Purpose

This document records the main third-party data sources that Brizel Health can connect to.

Brizel Health does **not** claim ownership over third-party food databases or third-party data retrieved from them.

## Open Food Facts

### Role In Brizel Health

- optional external food data source
- used for product metadata such as ingredients, allergens, labels, barcode-linked product information, and nutrition data when available

### Ownership And Licensing

- the Open Food Facts database is described by Open Food Facts as available under the Open Database License (ODbL)
- Open Food Facts also documents a separate content layer for database contents and media
- Open Food Facts documentation states that product images are available under Creative Commons Attribution ShareAlike

Official references:

- `https://world.openfoodfacts.org/data`
- `https://world.openfoodfacts.org/terms-of-use`
- `https://openfoodfacts.github.io/openfoodfacts-server/api/tutorial-off-api/`

### Important Compliance Note

Brizel Health does not claim any rights over Open Food Facts data.

If Open Food Facts data is reused, redistributed, or combined into public-facing derived databases, separate ODbL attribution and share-alike obligations may apply.

Brizel Health currently treats Open Food Facts as an external source, not as Brizel-owned content.

### Affiliation

Brizel Health is not affiliated with, endorsed by, or sponsored by Open Food Facts.

## USDA FoodData Central

### Role In Brizel Health

- optional external food data source
- used primarily for search, food details, and nutrient/hydration-oriented food import flows

### Ownership And Licensing

USDA FoodData Central states in its official API Guide that:

- FoodData Central data are in the public domain
- the data are published under CC0 1.0 Universal
- no permission is needed for use
- users are asked to cite FoodData Central as the source

Suggested source citation from USDA:

- U.S. Department of Agriculture, Agricultural Research Service. FoodData Central. `fdc.nal.usda.gov`

Official references:

- `https://fdc.nal.usda.gov/api-guide/`
- `https://fdc.nal.usda.gov/faq`

### Important Compliance Note

Brizel Health does not claim any rights over USDA FoodData Central data.

USDA data remain USDA-origin data even when imported into Brizel Health workflows.

### Affiliation

Brizel Health is not affiliated with, endorsed by, or sponsored by the U.S. Department of Agriculture.

## Home Assistant

### Role In Brizel Health

- host platform for the custom integration
- UI and automation runtime for Brizel Health entities, services, and frontend cards

### Notice

Brizel Health integrates with Home Assistant but is a separate project and repository.

This repository does not claim ownership of Home Assistant itself.

## No Transfer Of Third-Party Rights

Nothing in the Brizel Health repository license grants rights to third-party datasets, trademarks, logos, or content beyond the rights granted by the respective third party.
