import os
from pathlib import Path

import sst

# 4x prospero.prosperoCPU -> 4x private L1 -> shared Bus -> shared L2 -> memory

sst.setProgramOption("timebase", "1ps")
sst.setProgramOption("stop-at", "5s")

verbose = 0
clock_l1 = "3.5GHz"
prospero_clock = os.environ.get("PROSPERO_CLOCK", "2GHz")

cache_line_size = 64
num_cores = 4

protocol = "MESI"

opt_on_raw = os.environ.get("OPT_ON") or "0"
opt_on = str(opt_on_raw).strip().lower() in {"1", "true", "yes", "on"}
trace_dir = os.environ.get("PROSPERO_TRACE_DIR", None)
if not trace_dir:
    trace_dir = str(Path(__file__).resolve().parent / "prospero-traces")

trace_dir = str(trace_dir)

DEBUG_L1 = int(os.environ.get("DEBUG_L1", "0"))
DEBUG_L2 = int(os.environ.get("DEBUG_L2", "0"))
DEBUG_BUS = int(os.environ.get("DEBUG_BUS", "0"))
DEBUG_MEM = int(os.environ.get("DEBUG_MEM", "0"))
DEBUG_LEVEL = int(os.environ.get("DEBUG_LEVEL", "10"))

cpu_obj = []
l1_obj = []

for core_id in range(num_cores):
    trace_file = f"{trace_dir}/prospero_core{core_id}.trace"

    cpu = sst.Component(f"cpu{core_id}", "prospero.prosperoCPU")
    cpu.addParams(
        {
            "verbose": str(verbose),
            "reader": "prospero.ProsperoTextTraceReader",
            "readerParams.file": trace_file,
            "cache_line_size": str(cache_line_size),
            "pagesize": "4096",
            "clock": prospero_clock,
            "max_outstanding": "1",  # keep each core strictly in-order wrt itself
            "max_issue_per_cycle": "1",
        }
    )
    cpu_obj.append(cpu)

    l1_params = {
        "access_latency_cycles": "3",
        "cache_frequency": clock_l1,
        "replacement_policy": "lru",
        "coherence_protocol": protocol,
        # Must be strings: Cache forwards coherence_opt via find<std::string> to the MESI_L1 subcomponent;
        # integer 0/1 is not visible to that lookup and silently becomes "false".
        "coherence_opt": "true" if opt_on else "false",
        "associativity": "4",
        "cache_line_size": str(cache_line_size),
        "L1": "1",
        "cache_size": "16KiB",
        "debug": DEBUG_L1,
        "debug_level": DEBUG_LEVEL,
        "verbose": verbose,
    }

    l1 = sst.Component(f"l1cache{core_id}", "memHierarchy.Cache")
    l1.addParams(l1_params)
    l1_obj.append(l1)

l2_params = {
    "access_latency_cycles": "10",
    "cache_frequency": clock_l1,
    "replacement_policy": "lru",
    "coherence_protocol": protocol,
    "associativity": "12",
    "cache_line_size": str(cache_line_size),
    "cache_size": "384KiB",
    "debug": DEBUG_L2,
    "debug_level": DEBUG_LEVEL,
    "verbose": verbose,
}
l2cache = sst.Component("l2cache", "memHierarchy.Cache")
l2cache.addParams(l2_params)

# Read snarfing relies on snooping peer responses on a broadcast bus.
bus_params = {
    "bus_frequency": clock_l1,
    "broadcast": 1 if opt_on else 0,
    "debug": DEBUG_BUS,
    "debug_level": DEBUG_LEVEL,
}
bus = sst.Component("bus", "memHierarchy.Bus")
bus.addParams(bus_params)

mem_params = {
    "clock": "1GHz",
    "verbose": verbose,
    "addr_range_end": 512 * 1024 * 1024 - 1,
    "debug": DEBUG_MEM,
    "debug_level": DEBUG_LEVEL,
}
memctrl = sst.Component("memory", "memHierarchy.MemController")
memctrl.addParams(mem_params)

memory = memctrl.setSubComponent("backend", "memHierarchy.simpleMem")
memory.addParams({"access_time": "1000ns", "mem_size": "512MiB"})

# Links
for core_id in range(num_cores):
    link_cpu_l1 = sst.Link(f"link_cpu{core_id}_l1{core_id}")
    link_cpu_l1.connect((cpu_obj[core_id], "cache_link", "500ps"), (l1_obj[core_id], "highlink", "500ps"))

    link_l1_bus = sst.Link(f"link_l1{core_id}_bus{core_id}")
    link_l1_bus.connect((l1_obj[core_id], "lowlink", "500ps"), (bus, f"highlink{core_id}", "500ps"))

link_bus_l2 = sst.Link("link_bus_l2cache")
link_bus_l2.connect((bus, "lowlink0", "500ps"), (l2cache, "highlink", "500ps"))

link_l2_mem = sst.Link("link_l2_mem")
link_l2_mem.connect((l2cache, "lowlink", "500ps"), (memctrl, "highlink", "500ps"))

sst.setStatisticLoadLevel(0)
#sst.setStatisticOutput(std.statOutputTXT)
#sst.enableAllStatisticsForAllComponents()
print(
    f"[prospero-test] cores={num_cores} protocol={protocol} opt_on={opt_on}"
)

