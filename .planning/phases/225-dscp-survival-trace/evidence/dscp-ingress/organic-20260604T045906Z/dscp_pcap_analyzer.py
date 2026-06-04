#!/usr/bin/env python3
import argparse
import collections
import os
import struct
import sys


def pcap_reader(path):
    with open(path, "rb") as fh:
        header = fh.read(24)
        if len(header) < 24:
            return
        magic = header[:4]
        if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
            endian = "<"
        elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
            endian = ">"
        else:
            raise SystemExit(f"unsupported capture format (expected classic pcap): {path}")
        _magic, _vmaj, _vmin, _zone, _sig, _snap, linktype = struct.unpack(endian + "IHHIIII", header)
        while True:
            rec = fh.read(16)
            if len(rec) == 0:
                break
            if len(rec) < 16:
                raise SystemExit(f"truncated pcap record header: {path}")
            ts_sec, ts_usec, incl_len, _orig_len = struct.unpack(endian + "IIII", rec)
            payload = fh.read(incl_len)
            if len(payload) < incl_len:
                raise SystemExit(f"truncated pcap packet: {path}")
            yield linktype, ts_sec, ts_usec, payload


def parse_ip_packet(linktype, frame):
    if linktype == 1:  # Ethernet
        if len(frame) < 14:
            return None
        offset = 14
        ethertype = int.from_bytes(frame[12:14], "big")
        while ethertype in (0x8100, 0x88A8, 0x9100):
            if len(frame) < offset + 4:
                return None
            ethertype = int.from_bytes(frame[offset + 2:offset + 4], "big")
            offset += 4
    elif linktype == 113:  # Linux cooked v1
        if len(frame) < 16:
            return None
        offset = 16
        ethertype = int.from_bytes(frame[14:16], "big")
    elif linktype == 276:  # Linux cooked v2
        if len(frame) < 20:
            return None
        offset = 20
        ethertype = int.from_bytes(frame[0:2], "big")
    elif linktype in (101, 228):  # raw IPv4/IPv6-ish
        offset = 0
        version = frame[0] >> 4 if frame else 0
        ethertype = 0x0800 if version == 4 else 0x86DD if version == 6 else 0
    else:
        return None

    if ethertype == 0x0800:
        if len(frame) < offset + 20:
            return None
        tos = frame[offset + 1]
        ihl = (frame[offset] & 0x0F) * 4
        if ihl < 20 or len(frame) < offset + ihl:
            return None
        total_len = int.from_bytes(frame[offset + 2:offset + 4], "big") or max(0, len(frame) - offset)
        proto = frame[offset + 9]
        src = ".".join(str(b) for b in frame[offset + 12:offset + 16])
        dst = ".".join(str(b) for b in frame[offset + 16:offset + 20])
        ports = (None, None)
        if proto in (6, 17) and len(frame) >= offset + ihl + 4:
            ports = (
                int.from_bytes(frame[offset + ihl:offset + ihl + 2], "big"),
                int.from_bytes(frame[offset + ihl + 2:offset + ihl + 4], "big"),
            )
        return {"dscp": tos >> 2, "bytes": total_len, "proto": proto, "src": src, "dst": dst, "ports": ports}

    if ethertype == 0x86DD:
        if len(frame) < offset + 40:
            return None
        first_word = int.from_bytes(frame[offset:offset + 4], "big")
        traffic_class = (first_word >> 20) & 0xFF
        payload_len = int.from_bytes(frame[offset + 4:offset + 6], "big")
        next_header = frame[offset + 6]
        src = ":".join(f"{int.from_bytes(frame[offset + 8 + i:offset + 10 + i], 'big'):x}" for i in range(0, 16, 2))
        dst = ":".join(f"{int.from_bytes(frame[offset + 24 + i:offset + 26 + i], 'big'):x}" for i in range(0, 16, 2))
        ports = (None, None)
        l4 = offset + 40
        if next_header in (6, 17) and len(frame) >= l4 + 4:
            ports = (int.from_bytes(frame[l4:l4 + 2], "big"), int.from_bytes(frame[l4 + 2:l4 + 4], "big"))
        return {"dscp": traffic_class >> 2, "bytes": payload_len + 40, "proto": next_header, "src": src, "dst": dst, "ports": ports}

    return None


def summarize(path):
    hist = collections.Counter()
    byte_hist = collections.Counter()
    active = set()
    tuples = collections.Counter()
    total = 0
    total_bytes = 0
    for linktype, ts_sec, _ts_usec, frame in pcap_reader(path):
        parsed = parse_ip_packet(linktype, frame)
        if parsed is None:
            continue
        total += 1
        total_bytes += parsed["bytes"]
        active.add(ts_sec)
        dscp = parsed["dscp"]
        hist[dscp] += 1
        byte_hist[dscp] += parsed["bytes"]
        src_port, dst_port = parsed["ports"]
        if src_port is not None and dst_port is not None:
            tuples[(parsed["proto"], parsed["src"], src_port, parsed["dst"], dst_port)] += 1
    return hist, byte_hist, total, total_bytes, len(active), tuples


def write_histogram(args):
    hist, byte_hist, total, total_bytes, active_seconds, _tuples = summarize(args.pcap)
    nonbe_packets = sum(count for dscp, count in hist.items() if dscp != 0)
    nonbe_bytes = sum(count for dscp, count in byte_hist.items() if dscp != 0)
    pkt_pct = (nonbe_packets / total * 100.0) if total else 0.0
    byte_pct = (nonbe_bytes / total_bytes * 100.0) if total_bytes else 0.0
    valid = total >= args.min_packets and active_seconds >= args.min_active_seconds
    with open(args.output, "w") as out:
        out.write(f"CHANNEL={args.channel}\n")
        out.write(f"TOTAL_IP_PACKETS={total}\n")
        out.write(f"TOTAL_IP_BYTES={total_bytes}\n")
        out.write(f"ACTIVE_SECONDS={active_seconds}\n")
        out.write(f"NONBE_PKT_PCT={pkt_pct:.3f}\n")
        out.write(f"NONBE_BYTE_PCT={byte_pct:.3f}\n")
        out.write(f"WINDOW_VALID={str(valid).lower()}\n")
        out.write("DSCP PACKETS BYTES PACKET_PCT BYTE_PCT\n")
        for dscp in sorted(hist):
            packet_pct = (hist[dscp] / total * 100.0) if total else 0.0
            bytes_pct = (byte_hist[dscp] / total_bytes * 100.0) if total_bytes else 0.0
            out.write(f"DSCP_{dscp} {hist[dscp]} {byte_hist[dscp]} {packet_pct:.3f} {bytes_pct:.3f}\n")
    return total, total_bytes, active_seconds, pkt_pct, byte_pct, valid


def probe_summary(args):
    hist, _byte_hist, total, _total_bytes, _active, tuples = summarize(args.pcap)
    src_total = 0
    src_ef = 0
    src_match = False
    source_exists = bool(args.source_pcap and os.path.exists(args.source_pcap))
    if source_exists:
        src_hist, _src_bytes, src_total, _src_total_bytes, _src_active, src_tuples = summarize(args.source_pcap)
        src_ef = src_hist.get(46, 0)
        if tuples and src_tuples:
            src_match = bool(set(tuples) & set(src_tuples))
    ef = hist.get(46, 0)
    survival_pct = (ef / total * 100.0) if total else 0.0
    src_ef_pct = (src_ef / src_total * 100.0) if src_total else 0.0
    source_proven = source_exists and src_total >= 100 and src_ef_pct >= 90.0 and src_match
    if total < 100:
        survived = "degraded"
    elif args.direction == "dl" and not source_proven:
        survived = "degraded"
    elif survival_pct >= 90.0:
        survived = "true"
    elif survival_pct < 10.0:
        survived = "false"
    else:
        survived = "degraded"
    top_tuple = "unknown"
    if tuples:
        proto, src, sport, dst, dport = tuples.most_common(1)[0][0]
        proto_name = {6: "tcp", 17: "udp"}.get(proto, str(proto))
        top_tuple = f"{proto_name} {src}:{sport}->{dst}:{dport}"
    with open(args.output, "w") as out:
        out.write(f"CHANNEL={args.direction}_ef_probe\n")
        out.write(f"PROBE_5TUPLE={top_tuple}\n")
        out.write(f"PROBE_PROTO={args.probe_proto}\n")
        out.write(f"PROBE_PORT={args.probe_port}\n")
        out.write(f"PROBE_PKTS_SENT={args.probe_packets_sent}\n")
        out.write(f"PROBE_PKTS_CAPTURED={total}\n")
        out.write(f"EF_PKTS_AT_ENQUEUE={ef}\n")
        out.write(f"EF_SURVIVAL_PCT={survival_pct:.3f}\n")
        if args.direction == "dl":
            out.write(f"SRC_PROBE_PKTS_TOTAL={src_total}\n")
            out.write(f"SRC_EF_PKTS={src_ef}\n")
            out.write(f"EF_PKTS_AT_SOURCE={src_ef}\n")
            out.write(f"SRC_EF_PCT={src_ef_pct:.3f}\n")
            out.write(f"SRC_CAPTURE_POINT={args.source_capture_point}\n")
            out.write(f"SRC_ENQUEUE_5TUPLE_MATCH={str(src_match).lower()}\n")
            out.write(f"DL_SOURCE_EF_PROVEN={str(source_proven).lower()}\n")
        out.write(f"EF_SURVIVED={survived}\n")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    hist = sub.add_parser("histogram")
    hist.add_argument("--pcap", required=True)
    hist.add_argument("--output", required=True)
    hist.add_argument("--channel", required=True)
    hist.add_argument("--min-packets", type=int, required=True)
    hist.add_argument("--min-active-seconds", type=int, required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("--pcap", required=True)
    probe.add_argument("--output", required=True)
    probe.add_argument("--direction", choices=("dl", "ul"), required=True)
    probe.add_argument("--source-pcap", default="")
    probe.add_argument("--source-capture-point", default="unavailable")
    probe.add_argument("--probe-proto", required=True)
    probe.add_argument("--probe-port", required=True)
    probe.add_argument("--probe-packets-sent", default="unknown")
    args = parser.parse_args()
    if args.cmd == "histogram":
        write_histogram(args)
    elif args.cmd == "probe":
        probe_summary(args)


if __name__ == "__main__":
    main()
