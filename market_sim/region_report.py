"""Passive daily allocation of consumer revenue to catchment regions."""

import math


class RegionReporter:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.rows = []
        self.locations = []

    def start_year(self, runner):
        self.revenue = {}
        self.previous = {}
        self.weights = {}
        geo = runner.env.geography
        if not self.enabled or geo is None:
            return
        self.revenue = dict.fromkeys(geo.regions, 0.0)
        for firm in runner.network.firms_in("retailer"):
            self.previous[firm.id] = runner.env.runtimes[firm.id].revenue
            contributions = {}
            for name, place in geo.regions.items():
                distance = min(math.hypot(place.x - geo.regions[s].x, place.y - geo.regions[s].y)
                               * geo.cfg.road_factor for s in geo.sites(firm)) + geo.cfg.local_km
                contributions[name] = geo.population[name] / (1 + distance / geo.cfg.travel_km)
            total = sum(contributions.values())
            self.weights[firm.id] = {k: v / total for k, v in contributions.items()}

    def daily(self, runner):
        for firm_id, weights in self.weights.items():
            current = runner.env.runtimes[firm_id].revenue
            change = current - self.previous[firm_id]
            self.previous[firm_id] = current
            for region, weight in weights.items():
                self.revenue[region] += change * weight

    def finish_year(self, runner, year, summaries):
        geo = runner.env.geography
        if not self.enabled or geo is None:
            return
        active = [f for f in runner._firms() if runner.env.runtimes[f.id].active]
        population = sum(c.persons for c in runner.config.consumers.classes)
        for firm in active:
            self.locations.append(dict(year=year, firm=firm.id, region=firm.region,
                                       capacity=runner.env._effective_capacity(firm.id), stage=firm.stage))
        for region in geo.regions:
            retailers = [f for f in active if f.stage == "retailer" and region in geo.sites(f)]
            home = [f for f in retailers if f.region == region and summaries[f.id].revenue > 0]
            self.rows.append(dict(year=year, region=region, consumer_revenue=self.revenue[region],
                                  retail_capacity=sum(runner.env._effective_capacity(f.id) / len(geo.sites(f)) for f in retailers),
                                  retailers=len(retailers), population_share=geo.population[region],
                                  population=population * geo.population[region],
                                  mean_retail_margin=sum(summaries[f.id].profit / summaries[f.id].revenue for f in home) / len(home) if home else 0.0))
