"""Process-wide lock for job-metadata read-modify-write cycles.

Status updates read metadata.json, change it and write it back. The
background compression thread and a cancel request could interleave, so
the thread's stale copy overwrote "cancelled" and the job ran to
completion anyway. Serialising the cycles fixes this within a process
(the local driver). Across serverless instances it remains best effort.
"""

import threading

job_metadata_lock = threading.RLock()
