// ECE/CSC 406/506 Project 2: Part 1

#ifndef MEMHIERARCHY_COUNTERS_H
#define MEMHIERARCHY_COUNTERS_H

#include <string>
#include <sstream>
#include <unordered_map>

#include "sst/elements/memHierarchy/memTypes.h"

namespace SST { namespace MemHierarchy {

struct CounterBank {
    uint64_t invalidations_seen = 0;   // Inv/ForceInv/FetchInv style coherence invalidations observed
    uint64_t interventions = 0;        // Cache supplied data to another cache/directory
    uint64_t gets_sent = 0;            // Number of GetS requests sent by this cache
    uint64_t getx_sent = 0;            // Number of GetX requests sent by this cache
    uint64_t getsx_sent = 0;           // Number of GetSX requests sent by this cache
    uint64_t state_transitions = 0;    // Any recorded state transition
    uint64_t trans_I_to_S = 0;
    uint64_t trans_I_to_E = 0;
    uint64_t trans_I_to_M = 0;
    uint64_t trans_S_to_I = 0;
    uint64_t trans_S_to_E = 0;
    uint64_t trans_S_to_M = 0;
    uint64_t trans_E_to_I = 0;
    uint64_t trans_E_to_S = 0;
    uint64_t trans_E_to_M = 0;
    uint64_t trans_M_to_I = 0;
    uint64_t trans_M_to_S = 0;
    uint64_t trans_M_to_E = 0;
};

inline std::unordered_map<std::string, CounterBank>& counterBanksById() {
    static std::unordered_map<std::string, CounterBank> counters;
    return counters;
}

inline CounterBank& counter(const std::string& counter_id) {
    return counterBanksById()[counter_id];
}

inline void incInvalidation(const std::string& counter_id) {
    counter(counter_id).invalidations_seen++;
}

inline void incIntervention(const std::string& counter_id) {
    counter(counter_id).interventions++;
}

inline void incRequestSent(const std::string& counter_id, Command cmd) {
    CounterBank& c = counter(counter_id);
    if (cmd == Command::GetS) c.gets_sent++;
    else if (cmd == Command::GetX) c.getx_sent++;
    else if (cmd == Command::GetSX) c.getsx_sent++;
}

inline bool isMESIStable(State state) {
    return state == I || state == S || state == E || state == M;
}

inline State canonicalMESIState(State state) {
    if (state < LAST_STATE) state = NextState[state];
    return isMESIStable(state) ? state : NULLST;
}

inline void recordTransition(const std::string& counter_id, State from, State to) {
    CounterBank& c = counter(counter_id);
    const State from_mesi = canonicalMESIState(from);
    const State to_mesi = canonicalMESIState(to);
    if (from_mesi == NULLST || to_mesi == NULLST || from_mesi == to_mesi) return;
    c.state_transitions++;

    if (from_mesi == I) {
        if (to_mesi == S) c.trans_I_to_S++;
        else if (to_mesi == E) c.trans_I_to_E++;
        else if (to_mesi == M) c.trans_I_to_M++;
    } else if (from_mesi == S) {
        if (to_mesi == I) c.trans_S_to_I++;
        else if (to_mesi == E) c.trans_S_to_E++;
        else if (to_mesi == M) c.trans_S_to_M++;
    } else if (from_mesi == E) {
        if (to_mesi == I) c.trans_E_to_I++;
        else if (to_mesi == S) c.trans_E_to_S++;
        else if (to_mesi == M) c.trans_E_to_M++;
    } else if (from_mesi == M) {
        if (to_mesi == I) c.trans_M_to_I++;
        else if (to_mesi == S) c.trans_M_to_S++;
        else if (to_mesi == E) c.trans_M_to_E++;
    }
}

inline std::string summaryString(const std::string& counter_id) {
    const CounterBank& c = counter(counter_id);
    std::ostringstream os;
    os << "Counter"
       << "[" << counter_id << "]"
       << " inv=" << c.invalidations_seen
       << " interv=" << c.interventions
       << " getS_sent=" << c.gets_sent
       << " getX_sent=" << c.getx_sent
       << " getSX_sent=" << c.getsx_sent
       << " trans=" << c.state_transitions
       << " I->S=" << c.trans_I_to_S
       << " I->E=" << c.trans_I_to_E
       << " I->M=" << c.trans_I_to_M
       << " S->I=" << c.trans_S_to_I
       << " S->E=" << c.trans_S_to_E
       << " S->M=" << c.trans_S_to_M
       << " E->I=" << c.trans_E_to_I
       << " E->S=" << c.trans_E_to_S
       << " E->M=" << c.trans_E_to_M
       << " M->I=" << c.trans_M_to_I
       << " M->S=" << c.trans_M_to_S
       << " M->E=" << c.trans_M_to_E;
    return os.str();
}

}} // namespace SST::MemHierarchy

#endif // MEMHIERARCHY_COUNTERS_H
