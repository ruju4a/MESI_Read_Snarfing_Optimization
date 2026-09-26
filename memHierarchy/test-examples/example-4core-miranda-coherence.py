import os
import sst

#   4x miranda.BaseCPU -> 4x private L1 -> shared bus -> shared L2 -> memory

verbose = 2
clock = "3.5GHz"
cache_line_size = 64

num_cores = 4

# Debug controls (require sst-core built with --enable-debug)
DEBUG_L1 = 0
DEBUG_L2 = 0
DEBUG_BUS = 0
DEBUG_MEM = 0
DEBUG_LEVEL = 10

# Optional single-address watch (line-aligned)
WATCH_ADDR = 0x1000
WATCH_LINE = WATCH_ADDR & ~(cache_line_size - 1)
WATCH_ADDR_PARAM = f"[{WATCH_LINE}]"
USE_DEBUG_ADDR_FILTER = False

cpu_obj = []
l1_obj = []

# Workload selector for coherence experiments.
case = os.environ.get("MIRANDA_CASE", "shared_write_pingpong").strip()
allowed_cases = {
    "disjoint_writes",
    "disjoint_read_only",
    "disjoint_read_then_write",
    "single_line_read_sharing",
    "shared_read_only",
    "shared_write_pingpong",
    "mixed_rw_upgrade",
}
if case not in allowed_cases:
    raise ValueError(f"Unsupported MIRANDA_CASE '{case}'. Allowed: {sorted(allowed_cases)}")

protocol = os.environ.get("MIRANDA_PROTOCOL", "MSI").strip().upper()
allowed_protocols = {"MSI", "MESI"}
if protocol not in allowed_protocols:
    raise ValueError(f"Unsupported MIRANDA_PROTOCOL '{protocol}'. Allowed: {sorted(allowed_protocols)}")

print(f"[miranda-suite-bus] Running case: {case} (protocol={protocol})")

SHARED_LINES = 8             # shared region size in cache lines
REQS_PER_CORE = 2000

# Miranda CPU parameters
cpu_params = {
    "clock": clock,
    "verbose": 0,
    "max_reqs_cycle": 2,
    "maxmemreqpending": 32,
    "cache_line_size": cache_line_size,
}

for core_id in range(num_cores):
    cpu = sst.Component(f"core{core_id}", "miranda.BaseCPU")
    cpu.addParams(cpu_params)
    shared_start = WATCH_LINE
    shared_end = WATCH_LINE + (cache_line_size * SHARED_LINES)
    region_size = cache_line_size * SHARED_LINES

    if case == "disjoint_writes":
        # Give each core a private region to minimize coherence interactions.
        start = WATCH_LINE + (core_id * region_size)
        end = start + region_size
        gen = cpu.setSubComponent("generator", "miranda.SingleStreamGenerator")
        mem_op = "Write"
        gen.addParams(
            {
                "verbose": 0,
                "count": REQS_PER_CORE,
                "length": 8,
                "startat": start,
                "max_address": end,
                "memOp": mem_op,
            }
        )
    elif case == "disjoint_read_only":
        # Protocol contrast case: private reads should favor E-state in MESI.
        start = WATCH_LINE + (core_id * region_size)
        end = start + region_size
        gen = cpu.setSubComponent("generator", "miranda.SingleStreamGenerator")
        mem_op = "Read"
        gen.addParams(
            {
                "verbose": 0,
                "count": REQS_PER_CORE,
                "length": 8,
                "startat": start,
                "max_address": end,
                "memOp": mem_op,
            }
        )
    elif case == "disjoint_read_then_write":
        # Protocol contrast case: private read->write on same lines.
        # MESI should show E->M while MSI typically shows S->M upgrades.
        start = WATCH_LINE + (core_id * region_size)
        gen = cpu.setSubComponent("generator", "miranda.CopyGenerator")
        gen.addParams(
            {
                "verbose": 0,
                "read_start_address": start,
                "write_start_address": start,
                "operandwidth": 8,
                "request_count": SHARED_LINES * (cache_line_size // 8),
                "n_per_call": 2,
            }
        )
    elif case == "single_line_read_sharing":
        # Protocol contrast case: all cores repeatedly read one shared line.
        start = shared_start
        end = shared_start + cache_line_size
        gen = cpu.setSubComponent("generator", "miranda.SingleStreamGenerator")
        mem_op = "Read"
        gen.addParams(
            {
                "verbose": 0,
                "count": REQS_PER_CORE,
                "length": 8,
                "startat": start,
                "max_address": end,
                "memOp": mem_op,
            }
        )
    elif case == "shared_read_only":
        start = shared_start
        end = shared_end
        gen = cpu.setSubComponent("generator", "miranda.SingleStreamGenerator")
        mem_op = "Read"
        gen.addParams(
            {
                "verbose": 0,
                "count": REQS_PER_CORE,
                "length": 8,
                "startat": start,
                "max_address": end,
                "memOp": mem_op,
            }
        )
    elif case == "shared_write_pingpong":
        start = shared_start
        end = shared_end
        gen = cpu.setSubComponent("generator", "miranda.SingleStreamGenerator")
        mem_op = "Write"
        gen.addParams(
            {
                "verbose": 0,
                "count": REQS_PER_CORE,
                "length": 8,
                "startat": start,
                "max_address": end,
                "memOp": mem_op,
            }
        )
    else:  # mixed_rw_upgrade
        start = shared_start
        end = shared_end
        # Cores 0-1 warm lines with reads, cores 2-3 perform writes to same lines.
        gen = cpu.setSubComponent("generator", "miranda.SingleStreamGenerator")
        mem_op = "Read" if core_id < 2 else "Write"
        gen.addParams(
            {
                "verbose": 0,
                "count": REQS_PER_CORE,
                "length": 8,
                "startat": start,
                "max_address": end,
                "memOp": mem_op,
            }
        )
    cpu_obj.append(cpu)

# L1 caches (private)
l1_params = {
    "access_latency_cycles": "3",
    "cache_frequency": clock,
    "replacement_policy": "lru",
    "coherence_protocol": protocol,
    "associativity": "4",
    "cache_line_size": str(cache_line_size),
    "L1": "1",
    "cache_size": "16KiB",
    "debug": DEBUG_L1,
    "debug_level": DEBUG_LEVEL,
    "verbose": verbose,
}
if USE_DEBUG_ADDR_FILTER:
    l1_params["debug_addr"] = WATCH_ADDR_PARAM

for core_id in range(num_cores):
    l1 = sst.Component(f"l1cache{core_id}", "memHierarchy.Cache")
    l1.addParams(l1_params)
    l1_obj.append(l1)

# Shared L2 cache
l2_params = {
    "access_latency_cycles": "10",
    "cache_frequency": clock,
    "replacement_policy": "lru",
    "coherence_protocol": protocol,
    "associativity": "12",
    "cache_line_size": str(cache_line_size),
    "cache_size": "384KiB",
    "debug": DEBUG_L2,
    "debug_level": DEBUG_LEVEL,
    "verbose": verbose,
}
if USE_DEBUG_ADDR_FILTER:
    l2_params["debug_addr"] = WATCH_ADDR_PARAM

l2cache = sst.Component("l2cache", "memHierarchy.Cache")
l2cache.addParams(l2_params)

# Bus interconnect
bus_params = {
    "bus_frequency": clock,
    "debug": DEBUG_BUS,
    "debug_level": DEBUG_LEVEL,
}
if USE_DEBUG_ADDR_FILTER:
    bus_params["debug_addr"] = WATCH_ADDR_PARAM

bus = sst.Component("bus", "memHierarchy.Bus")
bus.addParams(bus_params)

# Memory controller + backend
mem_params = {
    "clock": "1GHz",
    "verbose": verbose,
    "addr_range_end": 512 * 1024 * 1024 - 1,
    "debug": DEBUG_MEM,
    "debug_level": DEBUG_LEVEL,
}
if USE_DEBUG_ADDR_FILTER:
    mem_params["debug_addr"] = WATCH_ADDR_PARAM

memctrl = sst.Component("memory", "memHierarchy.MemController")
memctrl.addParams(mem_params)

memory = memctrl.setSubComponent("backend", "memHierarchy.simpleMem")
memory.addParams(
    {
        "access_time": "1000ns",
        "mem_size": "512MiB",
    }
)

# Links: core -> L1
sst.setStatisticLoadLevel(3)
sst.setStatisticOutput("sst.statOutputConsole")
for core_id in range(num_cores):
    link_cpu_l1 = sst.Link(f"link_cpu_l1cache{core_id}")
    link_cpu_l1.connect((cpu_obj[core_id], "cache_link", "500ps"), (l1_obj[core_id], "highlink", "500ps"))
    sst.enableAllStatisticsForComponentName(f"core{core_id}")
    link_l1_bus = sst.Link(f"link_l1cache_bus{core_id}")
    link_l1_bus.connect((l1_obj[core_id], "lowlink", "500ps"), (bus, f"highlink{core_id}", "500ps"))

link_bus_l2 = sst.Link("link_bus_l2cache")
link_bus_l2.connect((bus, "lowlink0", "500ps"), (l2cache, "highlink", "500ps"))

link_l2_mem = sst.Link("link_l2_mem")
link_l2_mem.connect((l2cache, "lowlink", "500ps"), (memctrl, "highlink", "500ps"))
