"""Database plumbing shared by all eight bounded contexts.

Three things live here and nothing else: the shared :mod:`~prope.db.metadata`
naming convention, engine/sessionmaker construction, and the
:func:`~prope.db.session.workspace_transaction` tenant seam that every
repository in the project is written against (D-08).
"""
