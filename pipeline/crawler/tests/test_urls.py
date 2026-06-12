from lily_crawler.urls import classify, in_scope_appliance


def test_classify_part() -> None:
    assert classify("https://www.partselect.com/PS11752778-…-Door-Shelf-Bin.htm") == "part"


def test_classify_model_vs_section() -> None:
    assert classify("https://www.partselect.com/Models/WDT780SAEM1/") == "model"
    assert (
        classify("https://www.partselect.com/Models/WRS325FDAM04/Sections/Ice-Maker-Parts/")
        == "section"
    )


def test_classify_repair_index_and_symptom() -> None:
    assert classify("https://www.partselect.com/Repair/Refrigerator/") == "category"
    assert classify("https://www.partselect.com/Repair/Refrigerator/Door-Sweating/") == "symptom"


def test_classify_unknown() -> None:
    assert classify("https://www.partselect.com/Dishwasher-Parts.htm") == "other"


def test_appliance_scope() -> None:
    assert in_scope_appliance("https://www.partselect.com/Repair/Refrigerator/Leaking/")
    assert in_scope_appliance("https://www.partselect.com/Repair/Dishwasher/Noisy/")
    assert not in_scope_appliance("https://www.partselect.com/Repair/Microwave/Sparking/")
