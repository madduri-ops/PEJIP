"""Network data: imported first-degree connections and warm paths (spec 8.16 to 8.26).

The modules here are pure logic with no storage of their own: :mod:`.linkedin` reads a
LinkedIn Connections export, :mod:`.companies` resolves employer names to tracked
companies, :mod:`.seniority` reads a level from a title, and :mod:`.matching` finds
matured connections for a role. Network data raises Application Priority only; it is
never part of Fit.
"""
