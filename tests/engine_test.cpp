#include "llmatch/matching_engine.hpp"
#include "reference_engine.hpp"
#include "fixtures.hpp"
#include <gtest/gtest.h>
#include <cstring>
#include <limits>
#include <span>
#include <stdexcept>

namespace llmatch {
struct EngineTestAccess {
    template<class E> static void sequences(E& e, Sequence command, Sequence event) {
        e.command_seq_ = command; e.event_seq_ = event;
    }
    template<class E> static auto sequences(const E& e) {
        return std::pair{e.command_seq_, e.event_seq_};
    }
};
}
namespace {
using namespace llmatch;
template<class E> std::vector<Event> run(E& engine, const Command& command) {
    std::vector<Event> events(engine.required_event_capacity());
    const auto result = engine.process(command, events);
    if (result.status != ProcessStatus::Processed || result.event_count > events.size())
        throw std::runtime_error("unexpected process result in fixture");
    events.resize(result.event_count);
    engine.check_invariants();
    return events;
}
template<class T> class EngineTest : public ::testing::Test {};
using Engines = ::testing::Types<MatchingEngine, ReferenceEngine>;
TYPED_TEST_SUITE(EngineTest, Engines);

TYPED_TEST(EngineTest, HandCalculatedEventsAndEverySnapshot) {
    TypeParam engine({8,102,100}), second({8,102,100});
    for (const auto& step : fixtures::basic()) {
        SCOPED_TRACE(step.command.request);
        EXPECT_EQ(run(engine, step.command), step.events);
        EXPECT_EQ(engine.snapshot(), step.snapshot);
        EXPECT_EQ(run(second, step.command), step.events);
        EXPECT_EQ(second.snapshot(), step.snapshot);
    }
}

TYPED_TEST(EngineTest, ReusedOutputBufferHasNoStaleEventFields) {
    TypeParam engine({8,102,100});
    std::vector<Event> output(engine.required_event_capacity());
    for (const auto& step : fixtures::basic()) {
        std::vector<unsigned char> previous(output.size()*sizeof(Event));
        std::memcpy(previous.data(),output.data(),previous.size());
        const auto result=engine.process(step.command,output);
        ASSERT_EQ(result.status,ProcessStatus::Processed);
        ASSERT_EQ(result.event_count,step.events.size());
        EXPECT_EQ((std::vector<Event>(output.begin(),output.begin()+static_cast<std::ptrdiff_t>(result.event_count))),step.events);
        const auto offset=result.event_count*sizeof(Event);
        EXPECT_EQ(std::memcmp(previous.data()+offset,reinterpret_cast<unsigned char*>(output.data())+offset,previous.size()-offset),0);
        EXPECT_EQ(engine.snapshot(),step.snapshot);
    }
}

TYPED_TEST(EngineTest, ConservativeFullBookAdmissionAndFullMarketSweep) {
    TypeParam engine({1,102,100});
    run(engine,{1,1,LimitOrder{301,Side::Sell,100,5}});
    const auto before = engine.snapshot();
    const Command limit{2,1,LimitOrder{302,Side::Buy,101,5}};
    EXPECT_EQ(run(engine,limit),(std::vector<Event>{fixtures::rejected(limit,2,4,RejectReason::CapacityExceeded),fixtures::complete(limit,2,5,0,0,0,false)}));
    EXPECT_EQ(engine.snapshot(),before);
    EXPECT_EQ(run(engine,{2,2,LimitOrder{303,Side::Buy,99,5}})[0].reject_reason,RejectReason::CapacityExceeded);
    auto e=run(engine,{2,3,MarketOrder{304,Side::Buy,5}});
    ASSERT_EQ(e.size(),3U);
    EXPECT_EQ(e[1].maker_id,301U); EXPECT_EQ(e[1].price,100); EXPECT_EQ(e.back().filled_qty,5U);
    EXPECT_EQ(engine.snapshot(),BookSnapshot{});
}

TYPED_TEST(EngineTest, ReverseSidePriorityFifoAndRestingRemainder) {
    TypeParam engine({8,200,100});
    run(engine,{1,1,LimitOrder{11,Side::Buy,99,3}});
    run(engine,{2,1,LimitOrder{12,Side::Buy,101,2}});
    run(engine,{3,1,LimitOrder{13,Side::Buy,101,4}});
    auto e=run(engine,{4,1,LimitOrder{14,Side::Sell,100,8}});
    ASSERT_EQ(e.size(),5U);
    EXPECT_EQ(e[1].maker_id,12U); EXPECT_EQ(e[1].qty,2U); EXPECT_EQ(e[1].price,101);
    EXPECT_EQ(e[2].maker_id,13U); EXPECT_EQ(e[2].qty,4U); EXPECT_EQ(e[2].price,101);
    EXPECT_EQ(e[3].kind,EventKind::Rested); EXPECT_EQ(e[3].qty,2U);
    EXPECT_EQ(e.back().filled_qty+e.back().resting_qty+e.back().cancelled_qty,8U);
    const auto state=engine.snapshot();
    ASSERT_EQ(state.bids.size(),1U); ASSERT_EQ(state.asks.size(),1U);
    EXPECT_EQ(state.bids[0].price,99); EXPECT_EQ(state.asks[0].price,100);
    e=run(engine,{5,1,LimitOrder{15,Side::Buy,100,1}});
    EXPECT_EQ(e[1].price,100); EXPECT_EQ(engine.snapshot().asks[0].orders[0].remaining,1U);
}

TYPED_TEST(EngineTest, CancelMiddleAndPartialFillPreserveFifo) {
    TypeParam engine({8,200,100});
    for(OrderId id=1;id<=3;++id) run(engine,{1,id,LimitOrder{id,Side::Sell,100,5}});
    run(engine,{1,4,CancelOrder{2}});
    run(engine,{2,1,MarketOrder{10,Side::Buy,2}});
    auto e=run(engine,{2,2,MarketOrder{11,Side::Buy,7}});
    ASSERT_EQ(e.size(),4U);
    EXPECT_EQ(e[1].maker_id,1U); EXPECT_EQ(e[1].qty,3U);
    EXPECT_EQ(e[2].maker_id,3U); EXPECT_EQ(e[2].qty,4U);
    EXPECT_EQ(engine.snapshot().asks[0].orders[0].arrival_seq,3U);
    e=run(engine,{1,5,CancelOrder{3}});
    EXPECT_EQ(e[1].qty,1U); EXPECT_EQ(e.back().cancelled_qty,1U);
    EXPECT_EQ(run(engine,{1,6,CancelOrder{3}})[0].reject_reason,RejectReason::UnknownOrder);
    EXPECT_EQ(run(engine,{1,7,CancelOrder{1}})[0].reject_reason,RejectReason::UnknownOrder);
}

TYPED_TEST(EngineTest, SellSweepsMultipleBidPricesWithExactEvents) {
    TypeParam engine({8,200,100});
    run(engine,{1,1,LimitOrder{1,Side::Buy,99,3}});
    run(engine,{2,1,LimitOrder{2,Side::Buy,101,2}});
    run(engine,{3,1,LimitOrder{3,Side::Buy,100,4}});
    const Command c{4,1,LimitOrder{4,Side::Sell,98,8}};
    EXPECT_EQ(run(engine,c),(std::vector<Event>{
        fixtures::event(EventKind::Accepted,c,4,10),
        fixtures::trade(c,4,11,2,2,2,101,2),
        fixtures::trade(c,4,12,3,3,3,100,4),
        fixtures::trade(c,4,13,1,1,1,99,2),
        fixtures::complete(c,4,14,8,0,0)}));
    EXPECT_EQ(engine.snapshot(),(BookSnapshot{{{99,1,{{1,1,Side::Buy,99,1,1}}}}, {}}));
    const Command c2{4,2,LimitOrder{5,Side::Sell,98,2}};
    EXPECT_EQ(run(engine,c2),(std::vector<Event>{
        fixtures::event(EventKind::Accepted,c2,5,15),
        fixtures::trade(c2,5,16,1,1,1,99,1),
        fixtures::rested(c2,5,17,Side::Sell,98,1),
        fixtures::complete(c2,5,18,1,1,0)}));
    EXPECT_EQ(engine.snapshot(),(BookSnapshot{{},{{98,1,{{5,4,Side::Sell,98,1,5}}}}}));
}

TYPED_TEST(EngineTest, DuplicateAndOwnerRejectBeforeChangingBook) {
    TypeParam engine({8,200,100});
    run(engine,{1,1,LimitOrder{1,Side::Sell,100,5}});
    const auto before=engine.snapshot();
    EXPECT_EQ(run(engine,{2,1,LimitOrder{1,Side::Buy,101,5}})[0].reject_reason,RejectReason::DuplicateOrder);
    EXPECT_EQ(run(engine,{2,2,MarketOrder{1,Side::Buy,5}})[0].reject_reason,RejectReason::DuplicateOrder);
    EXPECT_EQ(run(engine,{2,3,CancelOrder{1}})[0].reject_reason,RejectReason::NotOwner);
    EXPECT_EQ(engine.snapshot(),before);
}

TYPED_TEST(EngineTest, IdReuseRequestReuseAndSelfTradeAreExplicit) {
    TypeParam engine({8,200,100});
    run(engine,{1,1,LimitOrder{1,Side::Sell,100,5}});
    auto e=run(engine,{1,1,MarketOrder{2,Side::Buy,5}});
    EXPECT_EQ(e[1].maker_client,1U); EXPECT_EQ(e[1].taker_client,1U);
    run(engine,{1,1,LimitOrder{1,Side::Buy,100,3}});
    EXPECT_EQ(engine.snapshot().bids[0].orders[0].arrival_seq,3U);
    e=run(engine,{1,1,CancelOrder{1}});
    EXPECT_EQ(e.back().cancelled_qty,3U);
    run(engine,{1,1,LimitOrder{1,Side::Buy,100,2}});
    EXPECT_EQ(engine.snapshot().bids[0].total_qty,2U);
}

TYPED_TEST(EngineTest, RejectionPriorityAndSequences) {
    TypeParam engine({1,200,100});
    run(engine,{1,1,LimitOrder{1,Side::Sell,100,5}});
    const auto before=engine.snapshot();
    const std::vector<std::pair<Command,RejectReason>> cases{
        {{0,0,LimitOrder{0,static_cast<Side>(9),-1,0}},RejectReason::InvalidClientId},
        {{1,0,LimitOrder{0,static_cast<Side>(9),-1,0}},RejectReason::InvalidRequestId},
        {{1,1,LimitOrder{0,static_cast<Side>(9),-1,0}},RejectReason::InvalidOrderId},
        {{1,1,LimitOrder{1,static_cast<Side>(9),-1,0}},RejectReason::InvalidSide},
        {{1,1,LimitOrder{1,Side::Buy,-1,0}},RejectReason::InvalidQuantity},
        {{1,1,LimitOrder{1,Side::Buy,-1,1}},RejectReason::InvalidPrice},
        {{1,1,LimitOrder{1,Side::Buy,100,1}},RejectReason::DuplicateOrder},
        {{1,1,LimitOrder{2,Side::Buy,100,1}},RejectReason::CapacityExceeded},
        {{1,1,CancelOrder{9}},RejectReason::UnknownOrder},
        {{2,1,CancelOrder{1}},RejectReason::NotOwner},
        {{1,1,MarketOrder{2,Side::Buy,101}},RejectReason::InvalidQuantity},
        {{1,1,LimitOrder{2,Side::Buy,201,1}},RejectReason::InvalidPrice},
        {{1,1,LimitOrder{2,Side::Buy,0,1}},RejectReason::InvalidPrice},
        {{1,1,LimitOrder{2,Side::Buy,std::numeric_limits<Price>::min(),1}},RejectReason::InvalidPrice}
    };
    Sequence cs=1,es=3;
    for(const auto& [cmd,reason]:cases) {
        ++cs;
        auto events=run(engine,cmd);
        EXPECT_EQ(events,(std::vector<Event>{fixtures::rejected(cmd,cs,es+1,reason),fixtures::complete(cmd,cs,es+2,0,0,0,false)}));
        es+=2;
        EXPECT_EQ(engine.snapshot(),before);
    }
}

TYPED_TEST(EngineTest, CallErrorsLeaveEveryOutputByteAndStateUnchanged) {
    TypeParam engine({2,200,100});
    run(engine,{1,1,LimitOrder{1,Side::Sell,100,5}});
    const auto before=engine.snapshot();
    std::vector<Event> output(engine.required_event_capacity());
    std::memset(output.data(),0xa5,output.size()*sizeof(Event));
    std::vector<unsigned char> bytes(output.size()*sizeof(Event));
    std::memcpy(bytes.data(),output.data(),bytes.size());
    const Command command{2,1,MarketOrder{2,Side::Buy,1}};
    const auto sequences_before=EngineTestAccess::sequences(engine);
    auto result=engine.process(command,std::span<Event>(output).first(output.size()-1));
    EXPECT_EQ(result,(ProcessResult{ProcessStatus::OutputBufferTooSmall,0}));
    EXPECT_EQ(std::memcmp(bytes.data(),output.data(),bytes.size()),0);
    EXPECT_EQ(engine.snapshot(),before);
    EXPECT_EQ(EngineTestAccess::sequences(engine),sequences_before);
    auto e=run(engine,command);
    EXPECT_EQ(e[0].command_seq,2U); EXPECT_EQ(e[0].event_seq,4U);
    const auto after=engine.snapshot();
    EngineTestAccess::sequences(engine,std::numeric_limits<Sequence>::max(),0);
    const auto exhausted_command=EngineTestAccess::sequences(engine);
    result=engine.process(command,output);
    EXPECT_EQ(result,(ProcessResult{ProcessStatus::SequenceExhausted,0}));
    EXPECT_EQ(std::memcmp(bytes.data(),output.data(),bytes.size()),0);
    EXPECT_EQ(engine.snapshot(),after);
    EXPECT_EQ(EngineTestAccess::sequences(engine),exhausted_command);
    EngineTestAccess::sequences(engine,0,std::numeric_limits<Sequence>::max()-engine.required_event_capacity()+1);
    const auto exhausted_event=EngineTestAccess::sequences(engine);
    result=engine.process(command,output);
    EXPECT_EQ(result,(ProcessResult{ProcessStatus::SequenceExhausted,0}));
    EXPECT_EQ(std::memcmp(bytes.data(),output.data(),bytes.size()),0);
    EXPECT_EQ(engine.snapshot(),after);
    EXPECT_EQ(EngineTestAccess::sequences(engine),exhausted_event);
    result=engine.process(command,{});
    EXPECT_EQ(result.status,ProcessStatus::OutputBufferTooSmall);
}

TYPED_TEST(EngineTest, LastRepresentableSequencesDoNotWrap) {
    TypeParam engine({1,200,100});
    const auto max=std::numeric_limits<Sequence>::max();
    EngineTestAccess::sequences(engine,max-1,max-engine.required_event_capacity());
    auto e=run(engine,{1,1,MarketOrder{1,Side::Buy,1}});
    EXPECT_EQ(e[0].command_seq,max);
    EXPECT_EQ(e.back().event_seq,max-2);
    std::vector<Event> output(engine.required_event_capacity());
    EXPECT_EQ(engine.process({1,2,CancelOrder{1}},output).status,ProcessStatus::SequenceExhausted);
}

TYPED_TEST(EngineTest, ConfigAndQuantityExtremes) {
    const auto max=std::numeric_limits<Quantity>::max();
    const std::vector<EngineConfig> invalid{
        {0,100,1},{1,0,1},{1,-1,1},{1,100,0},{2,100,max},
        {std::numeric_limits<std::size_t>::max(),100,1},
        {std::numeric_limits<std::size_t>::max()/sizeof(Event),100,1}
    };
    for(const auto config:invalid) EXPECT_THROW(TypeParam{config},std::invalid_argument);
    TypeParam engine({1,std::numeric_limits<Price>::max(),max});
    run(engine,{1,1,LimitOrder{1,Side::Sell,std::numeric_limits<Price>::max(),max}});
    auto e=run(engine,{2,1,MarketOrder{2,Side::Buy,max-1}});
    EXPECT_EQ(e.back().filled_qty,max-1);
    EXPECT_EQ(engine.snapshot().asks[0].total_qty,1U);
    e=run(engine,{1,2,CancelOrder{1}});
    EXPECT_EQ(e.back().cancelled_qty,1U);
}

TYPED_TEST(EngineTest, LimitAndMarketSweepFitConservativeBound) {
    constexpr std::size_t capacity=8;
    for(const bool market:{false,true}) {
        TypeParam engine({capacity,200,100});
        const std::size_t makers=market?capacity:capacity-1;
        for(std::size_t i=0;i<makers;++i)
            run(engine,{1,i+1,LimitOrder{i+1,Side::Sell,100+static_cast<Price>(i),1}});
        Command command{2,1,MarketOrder{100,Side::Buy,20}};
        if(!market) command.payload=LimitOrder{100,Side::Buy,200,20};
        const auto e=run(engine,command);
        EXPECT_EQ(e.size(),makers+3);
        EXPECT_LE(e.size(),engine.required_event_capacity());
        for(std::size_t i=0;i<makers;++i) EXPECT_EQ(e[i+1].maker_id,i+1);
        EXPECT_EQ(e.back().filled_qty,makers);
        EXPECT_EQ(e.back().resting_qty+e.back().cancelled_qty,20-makers);
    }
}
}
