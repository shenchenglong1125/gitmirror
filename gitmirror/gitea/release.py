import logging
import requests

logger = logging.getLogger('github-gitea-mirror')

def check_gitea_release_exists(gitea_token, gitea_url, gitea_owner, gitea_repo, tag_name):
    """Check if a release with the given tag already exists in Gitea"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/releases/tags/{tag_name}"
    try:
        response = requests.get(api_url, headers=headers)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def create_gitea_release(gitea_token, gitea_url, gitea_owner, gitea_repo, release_data):
    """Create a release in Gitea"""
    # Check if release already exists
    if check_gitea_release_exists(gitea_token, gitea_url, gitea_owner, gitea_repo, release_data.tag_name):
        logger.info(f"Release {release_data.tag_name} already exists in Gitea, skipping")
        # Verify existing release is complete if it has assets
        if release_data.assets and len(release_data.assets) > 0:
            if verify_gitea_release(gitea_token, gitea_url, gitea_owner, gitea_repo, release_data.tag_name, release_data.assets):
                logger.info(f"Existing release {release_data.tag_name} is complete and verified")
            else:
                logger.warning(f"Existing release {release_data.tag_name} is incomplete or broken, attempting to recreate")
                # Delete the existing release to recreate it
                delete_release(gitea_token, gitea_url, gitea_owner, gitea_repo, release_data.tag_name)
                # Continue with creation (don't return)
        else:
            return
    
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/releases"
    
    release_payload = {
        'tag_name': release_data.tag_name,
        'name': release_data.title,
        'body': release_data.body,
        'draft': release_data.draft,
        'prerelease': release_data.prerelease,
    }

    try:
        response = requests.post(api_url, headers=headers, json=release_payload)
        if response.status_code == 409:
            logger.info(f"Release {release_data.tag_name} already exists in Gitea, skipping")
            return
        
        response.raise_for_status()
        logger.info(f"Successfully created release {release_data.tag_name} in Gitea")
        
        # Mirror release assets if they exist
        if release_data.assets:
            gitea_release = response.json()
            asset_results = []
            for asset in release_data.assets:
                result = mirror_release_asset(gitea_token, gitea_url, gitea_owner, gitea_repo, 
                                  gitea_release['id'], asset)
                asset_results.append(result)
            
            # Log summary of asset mirroring
            total_assets = len(release_data.assets)
            successful_assets = sum(1 for r in asset_results if r)
            logger.info(f"Mirrored {successful_assets}/{total_assets} assets for release {release_data.tag_name}")
            
            # Verify the release is complete
            if successful_assets < total_assets:
                logger.warning(f"Some assets failed to mirror for release {release_data.tag_name}")
            
            # Verify the release
            if verify_gitea_release(gitea_token, gitea_url, gitea_owner, gitea_repo, release_data.tag_name, release_data.assets):
                logger.info(f"Release {release_data.tag_name} verification successful")
            else:
                logger.error(f"Release {release_data.tag_name} verification failed - release may be incomplete")
                
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating Gitea release {release_data.tag_name}: {e}")

def delete_release(gitea_token, gitea_url, gitea_owner, gitea_repo, tag_name):
    """Delete a release in Gitea"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    # First get the release ID
    api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/releases/tags/{tag_name}"
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to get release {tag_name} for deletion: {response.status_code}")
            return False
        
        release_id = response.json().get('id')
        if not release_id:
            logger.error(f"Failed to get release ID for {tag_name}")
            return False
        
        # Now delete the release
        delete_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/releases/{release_id}"
        delete_response = requests.delete(delete_url, headers=headers)
        
        if delete_response.status_code == 204:
            logger.info(f"Successfully deleted release {tag_name}")
            return True
        else:
            logger.error(f"Failed to delete release {tag_name}: {delete_response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting Gitea release {tag_name}: {e}")
        return False

def mirror_release_asset(gitea_token, gitea_url, gitea_owner, gitea_repo, release_id, asset):
    """Mirror a release asset from GitHub to Gitea"""
    headers = {
        'Authorization': f'token {gitea_token}',
    }
    
    try:
        # Get asset size
        asset_size_mb = asset.size / (1024 * 1024)
        logger.info(f"Downloading asset: {asset.name} ({asset_size_mb:.2f} MB)")
        
        # Calculate appropriate timeouts based on file size
        # Use at least 60 seconds for download and 120 seconds for upload
        # Add 30 seconds per 50MB for download and 60 seconds per 50MB for upload
        download_timeout = max(60, 30 * (asset_size_mb / 50))
        upload_timeout = max(120, 60 * (asset_size_mb / 50))
        
        logger.debug(f"Using download timeout of {download_timeout:.0f}s and upload timeout of {upload_timeout:.0f}s")
        
        # Download asset from GitHub with calculated timeout
        download_response = requests.get(asset.browser_download_url, timeout=download_timeout)
        download_response.raise_for_status()
        asset_content = download_response.content
        
        # Upload to Gitea
        upload_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/releases/{release_id}/assets"
        files = {
            'attachment': (asset.name, asset_content)
        }
        
        # Use calculated timeout for uploading
        response = requests.post(upload_url, headers=headers, files=files, timeout=upload_timeout)
        response.raise_for_status()
        
        logger.info(f"Successfully mirrored asset: {asset.name}")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"Timeout error mirroring asset {asset.name} - asset may be too large, consider increasing timeouts")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error mirroring asset {asset.name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error mirroring asset {asset.name}: {e}")
        return False

def verify_gitea_release(gitea_token, gitea_url, gitea_owner, gitea_repo, release_tag, github_assets):
    """Verify that a release in Gitea is complete and not broken due to failed uploads by comparing file sizes"""
    headers = {
        'Authorization': f'token {gitea_token}',
        'Content-Type': 'application/json',
    }
    
    api_url = f"{gitea_url}/api/v1/repos/{gitea_owner}/{gitea_repo}/releases/tags/{release_tag}"
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to get release {release_tag} from Gitea: {response.status_code}")
            return False
        
        gitea_release = response.json()
        gitea_assets = gitea_release.get('assets', [])
        
        # Check if all assets are present
        github_asset_names = [asset.name for asset in github_assets]
        gitea_asset_names = [asset.get('name') for asset in gitea_assets]
        
        missing_assets = set(github_asset_names) - set(gitea_asset_names)
        
        if missing_assets:
            logger.error(f"Release {release_tag} is incomplete. Missing assets: {', '.join(missing_assets)}")
            return False
        
        # Check if asset sizes match
        size_mismatches = []
        for github_asset in github_assets:
            matching_gitea_assets = [a for a in gitea_assets if a.get('name') == github_asset.name]
            if not matching_gitea_assets:
                continue
                
            gitea_asset = matching_gitea_assets[0]
            github_size = github_asset.size
            gitea_size = gitea_asset.get('size', 0)
            
            # Allow for small differences in size (sometimes metadata can change)
            size_difference = abs(github_size - gitea_size)
            if size_difference > 1024:  # More than 1KB difference
                logger.warning(f"Asset {github_asset.name} size mismatch: GitHub={github_size}, Gitea={gitea_size}")
                size_mismatches.append(github_asset.name)
        
        if size_mismatches:
            logger.error(f"Release {release_tag} verification failed. Assets with size mismatches: {', '.join(size_mismatches)}")
            return False
            
        if not missing_assets and not size_mismatches:
            logger.info(f"Release {release_tag} verification successful. All {len(github_asset_names)} assets present with matching sizes.")
            return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error verifying Gitea release {release_tag}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error verifying Gitea release {release_tag}: {e}")
    
    return False 