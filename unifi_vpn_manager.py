#!/usr/bin/env python3
"""
UniFi UCG Ultra VPN Client Manager

This script allows you to pause/resume VPN client connections on your UniFi UCG Ultra
router by interacting with the UniFi Network Controller API.

Usage:
    python unifi_vpn_manager.py --action [pause|resume|status] [--vpn-name VPN_NAME]

Requirements:
    - Python 3.6+
    - requests library
    - Access to UniFi Network Controller

Author: Assistant
License: MIT
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Dict, List, Optional, Any
import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class UniFiVPNManager:
    """Manages VPN clients on UniFi UCG Ultra devices."""
    
    def __init__(self, controller_url: str, username: str, password: str, site: str = "default", debug: bool = False):
        """
        Initialize the UniFi VPN Manager.
        
        Args:
            controller_url: URL of the UniFi Network Controller (e.g., https://192.168.1.1)
            username: UniFi admin username
            password: UniFi admin password
            site: UniFi site name (default: "default")
            debug: Enable debug logging (default: False)
        """
        self.controller_url = controller_url.rstrip('/')
        self.username = username
        self.password = password
        self.site = site
        self.debug = debug
        self.session = requests.Session()
        self.session.verify = False  # Disable SSL verification for self-signed certs
        self.csrf_token = None  # Store CSRF token for UCG Ultra
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging configuration based on debug mode."""
        if self.debug:
            log_level = logging.INFO
            handlers = [
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('unifi_vpn_manager.log')
            ]
        else:
            log_level = logging.ERROR
            handlers = [logging.FileHandler('unifi_vpn_manager.log')]
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers,
            force=True  # Override any existing configuration
        )
        self.logger = logging.getLogger(__name__)
    
    def login(self) -> bool:
        """
        Authenticate with the UniFi Network Controller.
        
        Returns:
            bool: True if login successful, False otherwise
        """
        login_url = f"{self.controller_url}/api/auth/login"
        login_data = {
            "username": self.username,
            "password": self.password,
            "remember": False
        }
        
        try:
            self.logger.info("Attempting to login to UniFi Controller...")
            response = self.session.post(login_url, json=login_data, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("Successfully authenticated with UniFi Controller")
                
                # Extract CSRF token if present in response headers
                self.csrf_token = response.headers.get('X-CSRF-Token')
                if self.csrf_token:
                    self.logger.info("CSRF token obtained")
                    
                return True
            else:
                self.logger.error(f"Login failed with status code: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error during login: {e}")
            return False
    
    def logout(self):
        """Logout from the UniFi Network Controller."""
        try:
            logout_url = f"{self.controller_url}/api/auth/logout"
            self.session.post(logout_url, timeout=10)
            self.logger.info("Logged out from UniFi Controller")
        except requests.exceptions.RequestException:
            pass  # Ignore logout errors
    
    def get_vpn_clients(self) -> List[Dict[str, Any]]:
        """
        Retrieve all VPN client configurations from networkconf endpoint.
        
        Returns:
            List[Dict]: List of VPN client configurations
        """
        vpn_url = f"{self.controller_url}/proxy/network/api/s/{self.site}/rest/networkconf"
        
        try:
            response = self.session.get(vpn_url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('data', [])
                self.logger.info(f"Found {len(items)} network configurations")
                
                vpn_clients = []
                
                # Filter for VPN client configurations
                for item in items:
                    item_name = item.get('name', '').lower()
                    item_purpose = item.get('purpose', '').lower()
                    
                    # Check if this is a VPN client configuration
                    # Prioritize actual VPN clients over WAN interfaces
                    is_vpn_client = (
                        # Actual VPN client configurations
                        item_purpose == 'vpn-client' or
                        # VPN-related names
                        'surfshark' in item_name or
                        'nordvpn' in item_name or
                        'expressvpn' in item_name or
                        'openvpn' in item_name or
                        'wireguard' in item_name or
                        ('vpn' in item_name and item_purpose != 'wan')  # Exclude regular WAN interfaces
                    )
                    
                    if is_vpn_client:
                        self.logger.info(f"Found VPN client: {item.get('name', 'Unknown')} (purpose: {item.get('purpose', 'Unknown')})")
                        vpn_clients.append(item)
                
                self.logger.info(f"Found {len(vpn_clients)} VPN client configurations")
                return vpn_clients
                
            else:
                self.logger.error(f"Failed to retrieve network configurations: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error retrieving VPN clients: {e}")
            return []
    
    def find_vpn_client(self, vpn_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find a specific VPN client configuration.
        
        Args:
            vpn_name: Name of the VPN client to find (optional)
            
        Returns:
            Dict: VPN client configuration or None if not found
        """
        vpn_clients = self.get_vpn_clients()
        
        # If no VPN name specified, prioritize actual VPN clients over WAN interfaces
        if not vpn_name and vpn_clients:
            # First, try to find a client with purpose 'vpn-client'
            for client in vpn_clients:
                if client.get('purpose') == 'vpn-client':
                    return client
            # If no vpn-client found, return the first one
            return vpn_clients[0]
        
        # Search for specific VPN by name
        for client in vpn_clients:
            if vpn_name and vpn_name.lower() in client.get('name', '').lower():
                return client
        
        return None
    
    def update_vpn_client(self, vpn_config: Dict[str, Any], enabled: bool) -> bool:
        """
        Update VPN client configuration to enable or disable it.
        
        Args:
            vpn_config: VPN client configuration dictionary
            enabled: True to enable, False to disable
            
        Returns:
            bool: True if update successful, False otherwise
        """
        vpn_id = vpn_config.get('_id')
        if not vpn_id:
            self.logger.error("VPN configuration missing ID")
            return False
        
        # Update the configuration
        updated_config = vpn_config.copy()
        updated_config['enabled'] = enabled
        
        update_url = f"{self.controller_url}/proxy/network/api/s/{self.site}/rest/networkconf/{vpn_id}"
        
        try:
            # Add CSRF token to headers if available
            headers = {}
            if self.csrf_token:
                headers['X-CSRF-Token'] = self.csrf_token
                
            response = self.session.put(update_url, json=updated_config, headers=headers, timeout=30)
            
            if response.status_code == 200:
                action = "enabled" if enabled else "disabled"
                self.logger.info(f"Successfully {action} VPN client: {vpn_config.get('name', 'Unknown')}")
                return True
            else:
                self.logger.error(f"Failed to update VPN client: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error updating VPN client: {e}")
            return False
    
    def get_vpn_status(self, vpn_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the current status of VPN client(s).
        
        Args:
            vpn_name: Name of specific VPN client (optional)
            
        Returns:
            Dict: Status information
        """
        if vpn_name:
            vpn_client = self.find_vpn_client(vpn_name)
            if vpn_client:
                return {
                    'name': vpn_client.get('name', 'Unknown'),
                    'enabled': vpn_client.get('enabled', False),
                    'type': vpn_client.get('type', 'Unknown'),
                    'id': vpn_client.get('_id', 'Unknown')
                }
            else:
                return {'error': f'VPN client "{vpn_name}" not found'}
        else:
            # Return status of all VPN clients
            vpn_clients = self.get_vpn_clients()
            status_list = []
            for client in vpn_clients:
                status_list.append({
                    'name': client.get('name', 'Unknown'),
                    'enabled': client.get('enabled', False),
                    'type': client.get('type', 'Unknown'),
                    'id': client.get('_id', 'Unknown')
                })
            return {'vpn_clients': status_list}
    
    def pause_vpn(self, vpn_name: Optional[str] = None) -> bool:
        """
        Pause (disable) a VPN client.
        
        Args:
            vpn_name: Name of VPN client to pause (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        vpn_client = self.find_vpn_client(vpn_name)
        if not vpn_client:
            self.logger.error(f"VPN client not found: {vpn_name or 'any'}")
            return False
        
        if not vpn_client.get('enabled', False):
            self.logger.info(f"VPN client '{vpn_client.get('name')}' is already disabled")
            return True
        
        return self.update_vpn_client(vpn_client, enabled=False)
    
    def resume_vpn(self, vpn_name: Optional[str] = None) -> bool:
        """
        Resume (enable) a VPN client.
        
        Args:
            vpn_name: Name of VPN client to resume (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        vpn_client = self.find_vpn_client(vpn_name)
        if not vpn_client:
            self.logger.error(f"VPN client not found: {vpn_name or 'any'}")
            return False
        
        if vpn_client.get('enabled', False):
            self.logger.info(f"VPN client '{vpn_client.get('name')}' is already enabled")
            return True
        
        return self.update_vpn_client(vpn_client, enabled=True)




def load_config(config_file: str = "unifi_config.json") -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Dict: Configuration parameters
    """
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config file: {e}")
    
    return {}


def create_sample_config(config_file: str = "unifi_config.json"):
    """Create a sample configuration file."""
    sample_config = {
        "controller_url": "https://192.168.1.1",
        "username": "admin",
        "password": "your_password_here",
        "site": "default",
        "debug": False
    }
    
    try:
        with open(config_file, 'w') as f:
            json.dump(sample_config, f, indent=4)
        print(f"Sample configuration file created: {config_file}")
        print("Please edit the file with your UniFi controller details.")
        print("Set 'debug': true to enable verbose logging.")
    except IOError as e:
        print(f"Error creating config file: {e}")


def main():
    """Main function to handle command line arguments and execute actions."""
    parser = argparse.ArgumentParser(
        description="Manage VPN clients on UniFi UCG Ultra",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show status of all VPN clients
    python unifi_vpn_manager.py --action status
    
    # Pause a specific VPN client
    python unifi_vpn_manager.py --action pause --vpn-name "MyVPN"
    
    # Resume a specific VPN client
    python unifi_vpn_manager.py --action resume --vpn-name "MyVPN"
    
    # Pause the first VPN client found
    python unifi_vpn_manager.py --action pause
    
    # Create sample configuration file
    python unifi_vpn_manager.py --create-config
        """
    )
    
    parser.add_argument(
        '--action',
        choices=['pause', 'resume', 'status'],
        help='Action to perform on VPN client'
    )
    
    parser.add_argument(
        '--vpn-name',
        help='Name of the VPN client (optional, uses first found if not specified)'
    )
    
    parser.add_argument(
        '--config',
        default='unifi_config.json',
        help='Configuration file path (default: unifi_config.json)'
    )
    
    parser.add_argument(
        '--create-config',
        action='store_true',
        help='Create a sample configuration file'
    )
    
    parser.add_argument(
        '--controller-url',
        help='UniFi Controller URL (overrides config file)'
    )
    
    parser.add_argument(
        '--username',
        help='UniFi username (overrides config file)'
    )
    
    parser.add_argument(
        '--password',
        help='UniFi password (overrides config file)'
    )
    
    parser.add_argument(
        '--site',
        default='default',
        help='UniFi site name (default: default)'
    )
    
    args = parser.parse_args()
    
    # Create sample config if requested
    if args.create_config:
        create_sample_config(args.config)
        return
    
    # Require action if not creating config
    if not args.action:
        parser.error("--action is required (unless using --create-config)")
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line arguments
    controller_url = args.controller_url or config.get('controller_url')
    username = args.username or config.get('username')
    password = args.password or config.get('password')
    site = args.site or config.get('site', 'default')
    debug = config.get('debug', False)
    
    # Validate required parameters
    if not all([controller_url, username, password]):
        print("Error: Missing required parameters.")
        print("Please provide --controller-url, --username, and --password")
        print("or create a configuration file using --create-config")
        sys.exit(1)
    
    # Initialize VPN manager
    vpn_manager = UniFiVPNManager(controller_url, username, password, site, debug)
    
    try:
        # Login to controller
        if not vpn_manager.login():
            print("Failed to authenticate with UniFi Controller")
            sys.exit(1)
        
        # Execute requested action
        success = False
        
        if args.action == 'status':
            status = vpn_manager.get_vpn_status(args.vpn_name)
            print(json.dumps(status, indent=2))
            success = True
            
        elif args.action == 'pause':
            success = vpn_manager.pause_vpn(args.vpn_name)
            if success:
                print(f"Successfully paused VPN client: {args.vpn_name or 'first found'}")
            else:
                print(f"Failed to pause VPN client: {args.vpn_name or 'first found'}")
                
        elif args.action == 'resume':
            success = vpn_manager.resume_vpn(args.vpn_name)
            if success:
                print(f"Successfully resumed VPN client: {args.vpn_name or 'first found'}")
            else:
                print(f"Failed to resume VPN client: {args.vpn_name or 'first found'}")
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        vpn_manager.logout()


if __name__ == "__main__":
    main() 