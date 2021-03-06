import numpy as np, os, math
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from multiprocessing import Pool, cpu_count

from squish import Simulation, ordered, DomainParams
from squish.common import OUTPUT_DIR
from script_tools import RC_SETTINGS, get_args, get_data, format_data

NAME = "MinOrderVEE"


def get_min_vee(n):
    domain = DomainParams(n, math.sqrt(n), math.sqrt(n), 4)
    e_hex = ordered.e_hex(domain)

    configs = ordered.configurations(domain)
    min_vee, min_config = 1e10, None

    for config in configs:
        try:
            rbar = ordered.avg_radius(domain, config)
        except:
            print(tuple(domain), config)

        vee = (
            2 * domain.w * domain.h
            + 2 * math.pi * domain.n * (domain.r ** 2 - 2 * domain.r * rbar)
        ) / domain.n - e_hex

        if vee < min_vee and vee >= 0:
            min_vee = vee
            min_config = config

    return (domain.n, min_vee, min_config)


def main():
    def f():
        data = {}
        ns = list(range(1000, 5001))
        with Pool(cpu_count()) as pool:
            for i, res in enumerate(pool.imap_unordered(get_min_vee, ns)):
                data[res[0]] = res[1:]

                hashes = int(21 * i / len(ns))
                print(
                    f'Processed N={res[0]} |{"#"*hashes}{" "*(20-hashes)}|'
                    + f" {i+1}/{len(ns)} simulations processed.",
                    flush=True,
                    end="\r",
                )

            print(flush=True)

        return format_data(
            data, key_name="N", col_names=["Minimum Ordered VEE", "Config"]
        )

    plt.rcParams.update(RC_SETTINGS)
    data = get_data(OUTPUT_DIR / "OrderedCache" / (NAME + ".pkl"), f)
    ns, min_order, min_config = (
        data["N"],
        100 * data["Minimum Ordered VEE"],
        data["Config"],
    )

    fig = plt.figure(figsize=(20, 15))
    gs = fig.add_gridspec(1, 1)
    ax = fig.add_subplot(gs[0])

    pad = 5
    mov_avgs = np.array(
        [np.mean(min_order[max(0, i - pad) : i + pad]) for i in range(len(min_order))]
    )

    ax.scatter(ns, mov_avgs, s=8)

    log_slope, _ = np.polyfit(np.log10(ns), np.log10(mov_avgs), 1)
    print(log_slope)

    def g(x, k):
        return k * (x ** log_slope)

    # return a * np.e ** (-b * (x - c))
    params, covs = curve_fit(g, ns, min_order, p0=[5000])
    ax.plot(np.arange(500, 5500), g(np.arange(500, 5500), *params), color="C1")

    print(params)

    ax.grid(zorder=0)

    ax.set_xlim(800, 5200)

    ax.set_xlabel("N")
    ax.set_ylabel(r"VEE $\left[\times 10^{2}\right]$")

    fig.savefig(OUTPUT_DIR / (NAME + ".png"))
    print(f"Wrote to {OUTPUT_DIR / (NAME + '.png')}")


if __name__ == "__main__":
    os.environ["QT_log10GING_RULES"] = "*=false"
    try:
        main()
    except KeyboardInterrupt:
        print("Program terminated by user.")
