"""Deterministic fictional examples of the consumer classes."""

import random


def generate_personas(config, seed, class_reports=(), brand_reports=()):
    cfg = config.personas
    if not cfg.enabled or not cfg.first_names or config.consumers is None:
        return []
    rows = {r["consumer_class"]: r for r in class_reports}
    brands = {r["brand"]: r for r in brand_reports}
    regions = config.geography.regions
    output = []
    for cls in config.consumers.classes:
        row = rows.get(cls.name, {})
        shares = row.get("category_shares", {})
        category = max(shares, key=shares.get) if any(shares.values()) else "beer"
        typical = brands.get(row.get("favourite_brand"), {}).get("name")
        if not typical:
            candidates = [b for b in brands.values() if b["category"] == category]
            typical = max(candidates, key=lambda b: (b["units_sold"], b["brand"]))["name"] if candidates else {"beer": "Bier", "wine": "Wein", "spirits": "Spirituosen"}.get(category, category)
        for gender in ("woman", "man"):
            rng = random.Random(f"personas-{seed}-{cls.name}-{gender}")
            age = rng.randint(*cfg.age_ranges[cls.age_group])
            job = rng.choice(cfg.jobs[cls.income_level])
            output.append(dict(consumer_class=cls.name, gender=gender,
                first_name=rng.choice(cfg.first_names[gender]), surname=rng.choice(cfg.surnames), age=age,
                region=rng.choices([r.name for r in regions], weights=[r.population_share for r in regions])[0] if regions else None,
                job=f"Pensioniert, zuvor {job}" if age >= cfg.age_ranges["65+"][0] else job,
                monthly_income_range=list(cfg.income_ranges[cls.income_level]),
                drinking_habit=cls.name.rsplit("_", 1)[-1], typical_brand=typical,
                priority_de=cfg.priorities[max(cls.weights.model_dump(), key=cls.weights.model_dump().get)]))
    return output
