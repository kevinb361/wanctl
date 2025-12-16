#!/bin/bash
# Analyze capacity map data and suggest floor values

LOG_FILE="/home/kevin/fusion_cake/capacity_map.csv"

if [ ! -f "$LOG_FILE" ]; then
    echo "Error: No capacity map data found at $LOG_FILE"
    echo "Run capacity_mapper.sh a few times to collect data first."
    exit 1
fi

echo "=== CAKE Capacity Map Analysis ==="
echo ""

# Count samples
TOTAL_SAMPLES=$(tail -n +2 "$LOG_FILE" | wc -l)
echo "Total samples: $TOTAL_SAMPLES"
echo ""

if [ "$TOTAL_SAMPLES" -lt 5 ]; then
    echo "Not enough data yet. Need at least 5 samples for meaningful analysis."
    exit 0
fi

echo "=== Throughput by Hour of Day ==="
echo "Hour | Avg Mbps | Min Mbps | Max Mbps | Avg RTT (ms) | Samples"
echo "-----+----------+----------+----------+--------------+--------"

for hour in $(seq -f "%02g" 0 23); do
    # Extract data for this hour
    HOUR_DATA=$(awk -F',' -v h="$hour" '$2 == h {print $3, $4}' "$LOG_FILE")

    if [ -n "$HOUR_DATA" ]; then
        AVG_MBPS=$(echo "$HOUR_DATA" | awk '{sum+=$1; count++} END {if(count>0) printf "%.1f", sum/count; else print "N/A"}')
        MIN_MBPS=$(echo "$HOUR_DATA" | awk 'NR==1 {min=$1} {if($1<min) min=$1} END {printf "%.1f", min}')
        MAX_MBPS=$(echo "$HOUR_DATA" | awk 'NR==1 {max=$1} {if($1>max) max=$1} END {printf "%.1f", max}')
        AVG_RTT=$(echo "$HOUR_DATA" | awk '{sum+=$2; count++} END {if(count>0) printf "%.1f", sum/count; else print "N/A"}')
        COUNT=$(echo "$HOUR_DATA" | wc -l)

        printf "%s   | %8s | %8s | %8s | %12s | %6d\n" "$hour" "$AVG_MBPS" "$MIN_MBPS" "$MAX_MBPS" "$AVG_RTT" "$COUNT"
    fi
done

echo ""
echo "=== Overall Statistics ==="

# Calculate overall stats (excluding header and N/A values)
ALL_THROUGHPUT=$(tail -n +2 "$LOG_FILE" | awk -F',' '$3 ~ /^[0-9.]+$/ {print $3}')
ALL_RTT=$(tail -n +2 "$LOG_FILE" | awk -F',' '$4 ~ /^[0-9.]+$/ {print $4}')

if [ -n "$ALL_THROUGHPUT" ]; then
    OVERALL_AVG=$(echo "$ALL_THROUGHPUT" | awk '{sum+=$1; count++} END {printf "%.1f", sum/count}')
    OVERALL_MIN=$(echo "$ALL_THROUGHPUT" | sort -n | head -1)
    OVERALL_MAX=$(echo "$ALL_THROUGHPUT" | sort -n | tail -1)
    PERCENTILE_25=$(echo "$ALL_THROUGHPUT" | sort -n | awk 'BEGIN{c=0} {a[c++]=$1} END{print a[int(c*0.25)]}')
    PERCENTILE_50=$(echo "$ALL_THROUGHPUT" | sort -n | awk 'BEGIN{c=0} {a[c++]=$1} END{print a[int(c*0.50)]}')
    PERCENTILE_75=$(echo "$ALL_THROUGHPUT" | sort -n | awk 'BEGIN{c=0} {a[c++]=$1} END{print a[int(c*0.75)]}')

    echo "Average throughput: ${OVERALL_AVG} Mbps"
    echo "Minimum throughput: ${OVERALL_MIN} Mbps"
    echo "Maximum throughput: ${OVERALL_MAX} Mbps"
    echo "25th percentile:    ${PERCENTILE_25} Mbps"
    echo "50th percentile:    ${PERCENTILE_50} Mbps (median)"
    echo "75th percentile:    ${PERCENTILE_75} Mbps"
fi

if [ -n "$ALL_RTT" ]; then
    RTT_AVG=$(echo "$ALL_RTT" | awk '{sum+=$1; count++} END {printf "%.1f", sum/count}')
    RTT_MIN=$(echo "$ALL_RTT" | sort -n | head -1)
    RTT_MAX=$(echo "$ALL_RTT" | sort -n | tail -1)

    echo ""
    echo "Average RTT under load: ${RTT_AVG} ms"
    echo "Best RTT under load:    ${RTT_MIN} ms"
    echo "Worst RTT under load:   ${RTT_MAX} ms"
fi

echo ""
echo "=== Suggested Floor Values ==="
echo ""

if [ -n "$PERCENTILE_25" ] && [ -n "$PERCENTILE_50" ]; then
    # Conservative: 25th percentile (works 75% of the time)
    CONSERVATIVE_FLOOR=$(printf "%.0f" "$PERCENTILE_25")
    # Balanced: Between 25th and 50th
    BALANCED_FLOOR=$(echo "($PERCENTILE_25 + $PERCENTILE_50) / 2" | bc)
    BALANCED_FLOOR=$(printf "%.0f" "$BALANCED_FLOOR")
    # Aggressive: 50th percentile (median)
    AGGRESSIVE_FLOOR=$(printf "%.0f" "$PERCENTILE_50")

    echo "Conservative floor: ${CONSERVATIVE_FLOOR} Mbps (25th percentile - handles 75% of conditions)"
    echo "Balanced floor:     ${BALANCED_FLOOR} Mbps (between 25th-50th percentile)"
    echo "Aggressive floor:   ${AGGRESSIVE_FLOOR} Mbps (median - may see more bloat during peaks)"
    echo ""
    echo "Recommendation: Start with conservative, adjust based on experience."
fi

echo ""
echo "=== Time-of-Day Analysis ==="
echo ""

# Define time periods
NIGHT_THROUGHPUT=$(awk -F',' '$2 >= 0 && $2 < 6 && $3 ~ /^[0-9.]+$/ {print $3}' "$LOG_FILE")
MORNING_THROUGHPUT=$(awk -F',' '$2 >= 6 && $2 < 12 && $3 ~ /^[0-9.]+$/ {print $3}' "$LOG_FILE")
AFTERNOON_THROUGHPUT=$(awk -F',' '$2 >= 12 && $2 < 18 && $3 ~ /^[0-9.]+$/ {print $3}' "$LOG_FILE")
EVENING_THROUGHPUT=$(awk -F',' '$2 >= 18 && $2 < 24 && $3 ~ /^[0-9.]+$/ {print $3}' "$LOG_FILE")

for period in "Night (00-06)" "Morning (06-12)" "Afternoon (12-18)" "Evening (18-24)"; do
    case "$period" in
        "Night"*) DATA="$NIGHT_THROUGHPUT" ;;
        "Morning"*) DATA="$MORNING_THROUGHPUT" ;;
        "Afternoon"*) DATA="$AFTERNOON_THROUGHPUT" ;;
        "Evening"*) DATA="$EVENING_THROUGHPUT" ;;
    esac

    if [ -n "$DATA" ]; then
        AVG=$(echo "$DATA" | awk '{sum+=$1; count++} END {printf "%.1f", sum/count}')
        MIN=$(echo "$DATA" | sort -n | head -1)
        SAMPLES=$(echo "$DATA" | wc -l)
        printf "%-20s Avg: %6.1f Mbps  Min: %6.1f Mbps  Samples: %d\n" "$period" "$AVG" "$MIN" "$SAMPLES"
    fi
done

echo ""
echo "Raw data available at: $LOG_FILE"
