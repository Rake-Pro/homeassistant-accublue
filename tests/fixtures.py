"""Real frames captured from the meter on 2026-09-10 (fw 2.26, serial 36951-0925).

Taken verbatim from IoT-Lab/devices/accublue-home/first-run-2026-09-10.log.jsonl.
The meter pads its attributes, so the frames on the wire are longer than the
39 status bytes and the 88 well bytes the protocol defines; the parsers read
only the defined prefix.
"""

# read of characteristic 1503 while the meter was idle
STATUS_IDLE_HEX = (
    "02010004000000000000000001000000b6ff021a00000600000033363935312d303932350000f7a440380710d7feb6a904583371d5df2ccc51b41806f33fde9f"
)

# status notification 2 seconds into a run: measuring, progress 2
STATUS_RUNNING_HEX = (
    "02050004b50ba60000000101000300010102021a00000600000033363935312d303932350000f7a440380710d7feb6a904583371d5df2ccc51b41806f33fde9f"
)

# the second run in the log: set 0 notify, then reads of set 1 and set 2
SET0_HEX = (
    "4025da4282236e1e3a426b243e408648c5108025415e1e1d0544f534d52e4b4d7226b53daf519d236729e45b5c10764660231e16224d5a07c74358556e22342eb35c0e5df64a09182a561e4e2551364ef758d31b6334175d1736fd191e110b2c076dfffcbf442f00c2a47d8f5a020802708fff1bbfacc3080274bfe3ae158647"
)
SET1_HEX = (
    "3825b742c8235e1e3d41fc1c01404b4802113e26365e1b1de343b434cc2e264c7f20c53d5f513724d329e05b4e102d46b5220516cc4b03048543da542b23252e515cf05cc74a7b170656f74cf055e54dd258ac1c3a34f95ce6feff418686120bc62dfe403cc74ae7fffdf759280011fea4edd710548621f77f5b6120981c04be"
)
SET2_HEX = (
    "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020637dcf23df1720018a2dfbf67f20bc4d40d9c1debc8a4034c0e8babb930089603036fbdfbf2561"
)

# what accublue.py computed from those frames for the chlorine sanitizer
EXPECTED_CHLORINE = {
    "free_chlorine": 0.54,
    "total_chlorine": 0.65,
    "combined_chlorine": 0.11,
    "alkalinity": 112.0,
    "ph": 7.9,
    "calcium_hardness": 354.0,
    "cyanuric_acid": 21.0,
    "copper": 0.8,
    "iron": 0.1,
    "phosphate": 2341.0,
}
