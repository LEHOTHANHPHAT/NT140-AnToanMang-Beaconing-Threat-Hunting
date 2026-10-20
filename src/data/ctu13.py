"""Member A implements the real-data adapter after checking source fields."""


def prepare_ctu13(input_path, dataset_id):
    """Do not map total bidirectional bytes to bytes_sent without checking meaning."""
    raise NotImplementedError(
        "CTU-13 adapter is planned for week 2. See docs/data-contract.md."
    )
