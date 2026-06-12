from __future__ import annotations

from app.domain.repositioning import plan_repositioning


def _uniform_cost(n: int) -> list[list[float]]:
    return [[0.0 if i == j else 1.0 for j in range(n)] for i in range(n)]


def test_no_moves_when_balanced() -> None:
    plan = plan_repositioning([1, 2], supply=[3, 3], forecast=[3, 3], cost_matrix=_uniform_cost(2))
    assert plan.moves == []
    assert plan.idle_after == 0 and plan.unmet_after == 0


def test_surplus_moves_to_deficit() -> None:
    plan = plan_repositioning([1, 2], supply=[5, 0], forecast=[1, 4], cost_matrix=_uniform_cost(2))
    assert sum(m.trucks for m in plan.moves) == 4
    assert plan.idle_before == 4 and plan.idle_after == 0
    assert plan.unmet_before == 4 and plan.unmet_after == 0


def test_picks_cheapest_source() -> None:
    # Zone 3 needs 2 trucks; zone 1 is far (cost 10), zone 2 is near (cost 1).
    cost = [
        [0.0, 5.0, 10.0],
        [5.0, 0.0, 1.0],
        [10.0, 1.0, 0.0],
    ]
    plan = plan_repositioning([1, 2, 3], supply=[2, 2, 0], forecast=[0, 0, 2], cost_matrix=cost)
    moved_from = {m.from_zone: m.trucks for m in plan.moves}
    assert moved_from.get(2) == 2  # cheaper neighbour supplies the deficit
    assert plan.move_cost == 2.0


def test_capacity_shortfall_leaves_unmet() -> None:
    plan = plan_repositioning([1, 2], supply=[1, 0], forecast=[0, 3], cost_matrix=_uniform_cost(2))
    assert plan.unmet_after == 2  # only one truck available to cover demand of 3


def test_flow_conservation() -> None:
    cost = _uniform_cost(3)
    plan = plan_repositioning([1, 2, 3], supply=[4, 0, 0], forecast=[0, 2, 1], cost_matrix=cost)
    total_in = sum(m.trucks for m in plan.moves)
    assert total_in == 3
    for z in plan.zones:
        assert z.final_supply == z.supply - _out(plan, z.zone_id) + _in(plan, z.zone_id)


def _out(plan, zone_id: int) -> int:
    return sum(m.trucks for m in plan.moves if m.from_zone == zone_id)


def _in(plan, zone_id: int) -> int:
    return sum(m.trucks for m in plan.moves if m.to_zone == zone_id)
