#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Installing L2 Motion Bed integration..."
mkdir -p /config/custom_components
rm -rf /config/custom_components/l2_motion
cp -R /integration/l2_motion /config/custom_components/l2_motion
bashio::log.info "Installation complete. Restart Home Assistant, then add L2 Motion Bed from Settings → Devices & services."
