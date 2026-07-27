"""D&D class mechanics.

Import concrete class mechanics from their owning modules.  The
package root intentionally performs no eager re-export composition: doing so
would make every leaf import initialize unrelated progression definitions and
their content bootstrap dependencies.
"""

__all__: tuple[str, ...] = ()
