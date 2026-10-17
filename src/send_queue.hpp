#pragma once

#include "llmatch/server.hpp"

#include <algorithm>
#include <cassert>
#include <deque>
#include <span>

namespace llmatch::detail {

// The observation baseline remains one frame per application write. A later
// candidate changes only batch_max_frames; it is not a runtime service mode.
inline constexpr std::size_t batch_max_frames = 16;
inline constexpr std::size_t batch_descriptor_capacity = 16;
inline constexpr std::size_t batch_max_bytes = 4096;
static_assert(batch_max_frames > 0 && batch_max_frames <= batch_descriptor_capacity);
static_assert(protocol::max_frame_size <= batch_max_bytes);

// Gateway-owned storage and accounting only. Socket operations, Connection
// ownership and server shutdown stay in MatchingServer::Connection.
class SendQueue {
public:
    SendQueue(ServerStats& stats, std::size_t limit) : stats_(stats), limit_(limit) {}
    SendQueue(const SendQueue&) = delete;
    SendQueue& operator=(const SendQueue&) = delete;

    bool closed() const { return closed_; }
    bool writing() const { return writing_; }
    bool empty() const { return outgoing_.empty(); }
    std::size_t size() const { return outgoing_.size(); }
    std::size_t bytes() const { return outgoing_bytes_; }

    // false means the incoming frame exceeds the original send bound. The
    // Connection then closes, accounting for the already-queued frames once.
    bool enqueue(const protocol::Frame& frame, bool business) {
        assert(!closed_);
        if (frame.size > limit_ - outgoing_bytes_) {
            ++stats_.discarded_frames;
            stats_.discarded_business_frames += business;
            return false;
        }
        outgoing_.push_back({frame, business});
        outgoing_bytes_ += frame.size;
        stats_.send_high_water = std::max(stats_.send_high_water, outgoing_bytes_);
        return true;
    }

    std::span<const boost::asio::const_buffer> begin_write() {
        assert(!closed_ && !writing_ && !outgoing_.empty());
        active_frames_ = 0;
        active_bytes_ = 0;
        for (const auto& item : outgoing_) {
            if (active_frames_ == batch_max_frames || item.frame.size > batch_max_bytes - active_bytes_) break;
            buffers_[active_frames_++] = boost::asio::buffer(item.frame.storage.data(), item.frame.size);
            active_bytes_ += item.frame.size;
        }
        assert(active_frames_ != 0 && active_bytes_ != 0);
        writing_ = true;
        ++stats_.write_operations;
        stats_.write_frames_submitted += active_frames_;
        stats_.write_bytes_submitted += active_bytes_;
        ++stats_.write_batch_frames[active_frames_];
        ++stats_.write_batch_bytes[(active_bytes_ - 1) / 256];
        return {buffers_.data(), active_frames_};
    }

    // Called by the actual composed async_write callback. An error leaves the
    // queue for Connection::close; an earlier close has already discarded it.
    void complete(boost::system::error_code error, std::size_t transferred) {
        assert(writing_ && transferred <= active_bytes_);
        ++stats_.write_callbacks;
        stats_.write_error_callbacks += bool(error);
        stats_.write_bytes_transferred += transferred;
        if (closed_ || error) {
            ++stats_.unconfirmed_write_callbacks;
            stats_.unconfirmed_write_bytes += transferred;
            auto remaining = transferred;
            for (std::size_t i = 0; i < active_frames_; ++i) {
                if (remaining < buffers_[i].size()) break;
                remaining -= buffers_[i].size();
                ++stats_.unconfirmed_write_complete_frames;
            }
        } else {
            assert(transferred == active_bytes_);
            stats_.written_frames += active_frames_;
            for (std::size_t i = 0; i < active_frames_; ++i) {
                stats_.written_business_frames += outgoing_.front().business;
                outgoing_.pop_front();
            }
            outgoing_bytes_ -= active_bytes_;
        }
        writing_ = false;
        active_frames_ = 0;
        active_bytes_ = 0;
        if (closed_) clear();
    }

    void close() {
        if (closed_) return;
        closed_ = true;
        stats_.discarded_frames += outgoing_.size();
        for (const auto& item : outgoing_) stats_.discarded_business_frames += item.business;
        // deque elements and member buffer descriptors stay valid until the
        // in-flight operation's callback, including after socket cancellation.
        if (!writing_) clear();
    }

private:
    struct Outgoing { protocol::Frame frame; bool business{}; };
    void clear() {
        outgoing_.clear();
        outgoing_bytes_ = 0;
    }

    ServerStats& stats_;
    std::size_t limit_;
    std::deque<Outgoing> outgoing_;
    std::size_t outgoing_bytes_{};
    std::array<boost::asio::const_buffer, batch_descriptor_capacity> buffers_{};
    std::size_t active_frames_{};
    std::size_t active_bytes_{};
    bool writing_{};
    bool closed_{};
};

} // namespace llmatch::detail
