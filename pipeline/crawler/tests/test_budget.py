from lily_crawler.budget import CrawlBudget


def test_default_split_sums_to_500() -> None:
    b = CrawlBudget()
    assert b.total() == 500
    # intentional: parts dominate (attributes for fully-covered models),
    # sections cover ~14/model, symptoms reserved, models a handful.
    assert (b.models, b.sections, b.parts, b.symptoms) == (4, 60, 400, 36)


def test_sub_budget_is_a_hard_stop() -> None:
    b = CrawlBudget(models=2, sections=0, parts=0, symptoms=0)
    assert b.try_spend("model") is True
    assert b.try_spend("model") is True
    assert b.try_spend("model") is False  # third model dropped
    assert b.spent("model") == 2


def test_categories_are_independent() -> None:
    b = CrawlBudget(models=1, sections=1, parts=1, symptoms=1)
    assert b.try_spend("part") is True
    assert b.try_spend("part") is False
    # exhausting parts does not touch sections
    assert b.try_spend("section") is True


def test_repair_index_shares_symptom_slice() -> None:
    b = CrawlBudget(symptoms=1)
    assert b.try_spend("category") is True
    assert b.try_spend("symptom") is False  # shared pool exhausted
