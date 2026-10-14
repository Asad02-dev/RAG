from typing_extensions import TypedDict


# Shared state of one review. Each parallel agent writes only its own field,
# so the three agents never overwrite each other.
class ReviewState(TypedDict):

    # Input: the submission to review, e.g. "1547612"
    submission_key: str

    # Written by the three parallel agents
    data_check: str
    history: str
    risk: str

    # Written by the merge step: the combined review and recommendation
    review: dict
