"""D&D class mechanics.

Import concrete class mechanics and factories from their owning modules.  The
package root intentionally performs no eager re-export composition: doing so
would make every leaf import initialize unrelated character factories and
their server content bootstrap dependencies.
"""

__all__: tuple[str, ...] = ()
