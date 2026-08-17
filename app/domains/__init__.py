"""Domain packages for the multi-domain KGA gateway.

Each domain (``finance`` this round; ``csc``/``legal``/``audit``/``hr`` reserved)
groups the third-party providers wrapped under a single URL prefix. A domain
exposes one aggregate router that mounts its provider subrouters; ``main.py``
mounts the domain router.
"""
