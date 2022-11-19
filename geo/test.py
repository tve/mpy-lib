from geo import Coord

pt_ctr = Coord((34, 422382), (-119, -705693))
pt_ne = Coord((34, 432274), (-119, -688863))
pt_se = Coord((34, 413221), (-119, -685458))
pt_sw = Coord((34, 397029), (-119, -730756))
pt_nw = Coord((34, 429573), (-119, -724364))
pt_near = Coord((34, 422326), (-119, -705658))


def check(name, td, tb, pt2):
    d = pt_ctr.approx_distance(pt2)
    b = pt_ctr.approx_bearing(pt2)
    d_pct = 100 * (d - td) / td
    b_pct = 100 * (b - tb) / tb
    print(f"true d_{name}={td} calc d_{name}={d} error={d-td}=({d_pct:.2f}%)")
    print(f"true b_{name}={tb} calc b_{name}={b} error={b-tb}=({b_pct:.2f}%)")
    (d, b) = pt_ctr.approx_dist_bearing(pt2)
    d_pct = 100 * (d - td) / td
    b_pct = 100 * (b - tb) / tb
    print(f"true d_{name}={td} calc d_{name}={d} error={d-td}=({d_pct:.2f}%)")
    print(f"true b_{name}={tb} calc b_{name}={b} error={b-tb}=({b_pct:.2f}%)")
    print()


# from center to ne
check("ne", 1895, 54+(31/60)+(20/3600), pt_ne)
check("se", 2117, 118+(45/60)+(12/3600), pt_se)
check("sw", 3638, 219+(12/60)+(29/3600), pt_sw)
check("nw", 1890, 295+(2/60)+(4/3600), pt_nw)
check("near", 7, 153+(7/60)+(50/3600), pt_near)

c1 = Coord((34, 29.9589), (-119, -49.0944))
if c1.lat[1] != 499315:
    print(f"lat={c1.lat[1]} should be 499315")
if c1.lon[1] != -818240:
    print(f"lon={c1.lon[1]} should be -818240")
