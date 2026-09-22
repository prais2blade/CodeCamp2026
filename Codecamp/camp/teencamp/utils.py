"""
teencamp/utils.py

Project utility functions.

NOTE:
------
Batch allocation is no longer implemented in this module.

The old implementation depended on:

    - BATCHES
    - BATCH_SIZE

Those constants have been removed.

Batch allocation is now handled entirely by
BatchAllocationService following the new
service-oriented architecture.

This module remains as a compatibility layer while
legacy views are being migrated.
"""

from teencamp.services.batch_service import BatchAllocationService


def next_batch(registration):
    """
    Compatibility wrapper.

    Legacy code may still call:

        next_batch(registration)

    Internally this now delegates to the new
    BatchAllocationService.

    Returns
    -------
    Batch | None
    """

    return BatchAllocationService.allocate(
        registration
    )