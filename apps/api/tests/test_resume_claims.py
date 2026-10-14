import pytest

from jobpilot.services.resumes.claims import new_claims, numbers, proper_nouns, vocabulary

VOCAB = vocabulary(["Billing Systems"])
SOURCE = "Built payment APIs in Python on Postgres for 1,200 merchants at Example Corp."


def test_numbers_are_normalised():
    assert numbers("Cut costs 40 % for 1,200 users, saving $3.5k") == {"40%", "1200", "$3.5k"}


def test_proper_nouns_ignore_sentence_starts():
    assert proper_nouns("Led migration to AWS. Worked with Stripe") == {"aws", "stripe"}


def test_faithful_rewording_has_no_claims():
    text = "Designed Python payment APIs on PostgreSQL serving 1200 merchants at Example Corp."
    assert new_claims(text, SOURCE, VOCAB, check_nouns=True) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Built payment APIs in Python for 1,200 merchants, cutting latency 40%.",
         "adds number(s) not in your verified entry: 40%"),
        ("Built payment APIs in Python and Kubernetes for 1,200 merchants.",
         "adds skill(s) not in your verified entry: kubernetes"),
        ("Built payment APIs in Python for 1,200 merchants at Google.",
         "adds name(s) not in your verified entry: google"),
    ],
)
def test_new_claims_are_reported(text, expected):
    assert new_claims(text, SOURCE, VOCAB, check_nouns=True) == [expected]


def test_library_skill_names_are_part_of_the_vocabulary():
    assert new_claims("Owned billing systems in Python.", "Owned payments in Python.", VOCAB,
                      check_nouns=False) == ["adds skill(s) not in your verified entry: billing systems"]
