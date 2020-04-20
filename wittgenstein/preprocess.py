import numpy as np
import pandas as pd

from wittgenstein.check import _check_any_datasets_not_empty


def preprocess_training_data(preprocess_params):

    # Get params
    trainset = preprocess_params["trainset"]
    y = preprocess_params["y"]
    class_feat = preprocess_params["class_feat"]
    pos_class = preprocess_params["pos_class"]
    user_requested_feature_names = preprocess_params["feature_names"]
    n_discretize_bins = preprocess_params["n_discretize_bins"]
    verbosity = preprocess_params["verbosity"]

    # STEP 0: ERROR CHECKING
    _check_valid_input_data(trainset, y, class_feat)

    # STEP 1: DETERMINE class_feat
    class_feat = _get_class_feat_name(class_feat, y)

    # STEP 2: BUILD DataFrame from X_or_Xy (and if necessary y). DO NOT MODIFY ORIGINAL DATA
    df = _convert_to_df(trainset, y, class_feat)

    # STEP 3: DEFINE pos_class
    pos_class = get_pos_class(df, class_feat, pos_class)

    # STEP 4: GET_OR_SET FEATURE NAMES
    df = _get_or_set_feature_names(
        df, class_feat, user_requested_feature_names=user_requested_feature_names
    )

    # STEP 5: INFER FEATURE DTYPES
    df = df.infer_objects()

    # STEP 6: BIN FIT_TRANSFORM, TRANSFORM, or NOTHING
    df, bin_transformer_ = _try_bin_fit_or_fittransform_(
        df,
        n_discretize_bins=n_discretize_bins,
        ignore_feats=[class_feat],
        verbosity=verbosity,
    )

    # ALL DONE
    return df, class_feat, pos_class, bin_transformer_


def preprocess_prediction_data(preprocess_params):

    X = preprocess_params["X"]
    class_feat = preprocess_params["class_feat"]
    pos_class = preprocess_params["pos_class"]
    user_requested_feature_names = preprocess_params["user_requested_feature_names"]
    selected_features_ = preprocess_params["selected_features_"]
    trainset_features_ = preprocess_params["trainset_features_"]
    bin_transformer_ = preprocess_params["bin_transformer_"]
    verbosity = preprocess_params["verbosity"]

    # STEP 0: ERROR CHECKING
    _check_valid_input_data(X, y=None, class_feat=class_feat, requires_label=False)

    # STEP 1: BUILD DataFrame from X_or_Xy (and if necessary y). DO NOT MODIFY ORIGINAL DATA
    df = _convert_to_df(X, y=None, class_feat=class_feat, requires_label=False)

    # STEP 2: CHECK THAT ALL MODEL FEAETURES ARE PRESENT IN X
    df = _get_or_set_feature_names(
        df,
        class_feat,
        user_requested_feature_names=user_requested_feature_names,
        selected_features_=selected_features_,
        trainset_features_=trainset_features_,
    )

    # STEP 3: ASK PANDAS TO CORRECT DTYPES
    df = df.infer_objects()

    # STEP 4: BIN, IF NECESSARY
    df, _ = _try_bin_fit_or_fittransform_(
        df,
        bin_transformer_=bin_transformer_,
        ignore_feats=[class_feat],
        verbosity=verbosity,
    )

    return df

def _preprocess_recalibrate_proba_data(preprocess_params):

    # Get params
    X_or_Xy = preprocess_params["X_or_Xy"]
    y = preprocess_params["y"]
    class_feat = preprocess_params["class_feat"]
    pos_class = preprocess_params["pos_class"]
    user_requested_feature_names = preprocess_params["user_requested_feature_names"]
    bin_transformer_ = preprocess_params["bin_transformer_"]
    verbosity = preprocess_params["verbosity"]

    # STEP 0: ERROR CHECKING
    _check_valid_input_data(X_or_Xy, y, class_feat)

    # STEP 2: BUILD DataFrame from X_or_Xy (and if necessary y). DO NOT MODIFY ORIGINAL DATA
    df = _convert_to_df(X_or_Xy, y, class_feat)

    # STEP 4: GET_OR_SET FEATURE NAMES
    df = _get_or_set_feature_names(
        df, class_feat, user_requested_feature_names=user_requested_feature_names
    )

    # STEP 5: INFER FEATURE DTYPES
    df = df.infer_objects()

    # STEP 6: BIN FIT_TRANSFORM, TRANSFORM, or NOTHING
    df, bin_transformer_ = _try_bin_fit_or_fittransform_(
        df,
        bin_transformer_=bin_transformer_,
        ignore_feats=[class_feat],
        verbosity=verbosity,
    )

    # ALL DONE
    return df


def _preprocess_y_score_data(y):
    """ Return python iterable of y values """

    def raise_wrong_ndim():
        raise IndexError(f"y input data has wrong number dimensions. It should have 1.")

    # If it's pandas or np...
    if hasattr(y, "ndim"):
        if y.ndim == 1:
            return y.tolist()
        else:
            raise_wrong_ndim()

    # Otherwise try for python iterable
    if hasattr(y, "__getitem__"):
        # No super clean way to check for 1D, but this should be pretty good
        if any([hasattr(item, "__getitem__") and type(item) is not str for item in y]):
            raise_wrong_ndim()
        else:
            return y

    # Otherwise, no idea what's going on
    else:
        raise TypeError(
            f"Could not identify valid type for y input data: {type(y)}. Recommended types are 1D python iterable, pandas Series, or 1D numpy array."
        )


def _check_valid_input_data(X_or_Xy, y=None, class_feat=None, requires_label=True):

    # Make sure there is data
    if not _check_any_datasets_not_empty([X_or_Xy]):
        raise ValueError("No data provided!")

    # If labels aren't needed, we're done
    if not requires_label:
        return

    # Ensure class feature is provided
    if (y is None) and (class_feat is None):
        raise ValueError("y or class_feat param is required")

    # Ensure target data exists if class feat is provided
    if y is None:
        # X_or_Xy is a df: does target column exist?
        if hasattr(X_or_Xy, "columns") and (class_feat not in X_or_Xy.columns):
            raise IndexError(f"Data does not contain class feature {class_feat}")
        # X_or_Xy is an array or iterable: does target index exist?
        elif not hasattr(X_or_Xy, "columns"):
            try:
                if int(class_feat) >= len(X_or_Xy[0]):
                    raise IndexError(
                        f"Class index {class_feat} out of range for trainset."
                    )
            except:
                raise IndexError(f"Class index {class_feat} out of range for trainset.")

    # Ensure no class feature name mismatch
    if (
        y is not None
        and class_feat is not None
        and hasattr(y, "name")
        and y.name != class_feat
    ):
        raise NameError(
            f"Feature name mismatch between params y {y.name} and class_feat {class_feat}. Besides, you only need to provide one of them."
        )

def _convert_to_df(X_or_Xy, y, class_feat, requires_label=True):
    """ Create a labeled trainset from input data. If original data was of pandas type, make deepcopy. """

    # Create df from X_or_Xy
    if isinstance(X_or_Xy, pd.DataFrame):
        df = X_or_Xy.copy()
    else:
        df = pd.DataFrame(X_or_Xy)

    # If necessary, merge y into df
    if y is not None:
        # If y is pd or np type, add it
        try:
            df = df.set_index(y.index)
            df[class_feat] = y.copy()
        # If that doesn't work, it's likely a python iterable
        except:
            df[class_feat] = y
    return df


def get_pos_class(df, class_feat, pos_class):

    # Pos class already known
    if pos_class:
        return pos_class

    # Check if pos class can be inferred as True or 1
    y_unique = df[class_feat].unique()
    if len(y_unique) == 2:
        class_labels = sorted(y_unique.tolist())
        if (
            class_labels[0] is 0 and class_labels[1] is 1
        ):  # 'is' operator is essential to distinguish 1,True, etc.
            return 1
        elif class_labels[0] is False and class_labels[1] is True:
            return True

    # Can't infer classes
    raise NameError(
        f"Couldn't infer name of positive target class from class feature: {class_feat}. Try using parameter pos_class to specify which class label should be treated as positive, or renaming your classes as booleans or 0,1."
    )


def _get_class_feat_name(class_feat, y):

    if class_feat is not None:
        return class_feat

    if y is not None and hasattr(y, "name"):
        # If y is a pandas Series, try to get its name
        class_feat = y.name
    else:
        # Create a name for it
        class_feat = "Class"

    return class_feat


def _get_or_set_feature_names(
    df,
    class_feat,
    user_requested_feature_names=None,
    selected_features_=None,
    trainset_features_=None,
):
    """ Assign feature names in order of these preferences:
        1) user_requested_feature_names
        2) fine if no missing features or no model has been trained
        3) trainset_features_ (if they exist)
    """

    # 1) User wants to rename features. Raise error if fail
    if (
        user_requested_feature_names is not None
        and len(user_requested_feature_names) > 0
    ):
        original_feat_names = [col for col in df.columns if col != class_feat]
        df = _try_rename_features(
            df, class_feat, user_requested_feature_names
        )  # Returns None if can't rename
        if df is not None:
            return df
        else:
            raise IndexError(
                f"The number of requested features names ({len(user_requested_feature_names)}) does not match the number of non-class features in dataset: ({len(original_feat_names)}).\nParam feature_names: {truncstr(user_requested_feature_names,10)}\nTraining set features names: {truncstr(original_feat_names,10)}"
            )

    # 2) If no model trained, use defaults
    if selected_features_ is None:
        return df

    # 3) Are all model features present? If so, we're good.
    missing_feats = _get_missing_selected_features(df, selected_features_)
    if not missing_feats:
        return df

    # 4) Some feats are missing: try to apply training data. Warn on success; raise error on fail
    if missing_feats:
        missing_feats_str = f"Some features selected by fit Ruleset model are missing: {missing_feats}.\nEither ensure prediction dataset includes all Ruleset-selected features with same names as training set, or use param feature_names to specify the names of dataset features.\nAttempted feature names:{truncstr(df.columns.tolist())}\n"
        df = _try_rename_features(
            df, class_feat, trainset_features_
        )  # returns None if feature length mismatch
        if df is not None:
            _warn(
                missing_feats_str,
                RuntimeWarning,
                filename="base_functions",
                funcname="_get_or_set_feature_names",
            )
            trainset_feats_str = f"Mismatch between Ruleset training feature names and prediction feature names:{truncstr(df.columns.tolist())}\nPredicting under on the assumption that the features provided for prediction are the same as those the model was trained on, and that they are being provided in the same order.\nYou probably want to ensure your prediction dataset includes the same feature names as your Ruleset selected features, or alternately, to use param feature_names to specify prediction feature names."
            _warn(
                trainset_feats_str,
                RuntimeWarning,
                filename="base_functions",
                funcname="_get_or_set_feature_names",
            )
            return df
        else:
            raise NameError(missing_feats_str)



def _try_bin_fit_or_fittransform_(
    df, ignore_feats=[], n_discretize_bins=None, bin_transformer_=None, verbosity=0
):

    # Binning has already been fit
    if bin_transformer_:
        bin_transform(df, bin_transformer_)
        return df, bin_transformer_

    # Binning disabled
    elif not n_discretize_bins:
        return df, bin_transformer_

    # Binning enabled, and binner needs to be fit
    else:
        df, bin_transformer_ = bin_df(
            df,
            n_discretize_bins=n_discretize_bins,
            ignore_feats=ignore_feats,
            verbosity=verbosity,
        )
        return df, bin_transformer_


def bin_df(df, n_discretize_bins=10, ignore_feats=[], verbosity=0):
    """ Returns df with seemingly numeric features binned, and the bin_transformer or None depending on whether binning takes places. """

    if n_discretize_bins is None:
        return df, None

    isbinned = False
    numeric_feats = find_numeric_feats(df, ignore_feats=ignore_feats)
    if numeric_feats:
        if n_discretize_bins:
            if verbosity == 1:
                print(f"binning data...\n")
            elif verbosity >= 2:
                print(f"binning features {numeric_feats}...")
            binned_df = df.copy()
            bin_transformer = fit_bins(
                binned_df,
                n_bins=n_discretize_bins,
                output=False,
                ignore_feats=ignore_feats,
                verbosity=verbosity,
            )
            binned_df = bin_transform(binned_df, bin_transformer)
            isbinned = True
        else:
            n_unique_values = sum(
                [len(u) for u in [df[f].unique() for f in numeric_feats]]
            )
            warning_str = f"There are {len(numeric_feats)} apparent numeric features: {numeric_feats}. \n Treating {n_unique_values} numeric values as nominal. To auto-discretize features, assign a value to parameter 'n_discretize_bins.'"
            _warn(warning_str, RuntimeWarning, filename="base", funcname="bin_df")
    if isbinned:
        return binned_df, bin_transformer
    else:
        return df, None


def find_numeric_feats(df, ignore_feats=[]):
    """ Returns df features that seem to be numeric. """
    numeric_feats = df.select_dtypes(np.number)
    numeric_feats = [f for f in numeric_feats if f not in ignore_feats]
    return numeric_feats


def fit_bins(df, n_bins=5, output=False, ignore_feats=[], verbosity=0):
    """
    Returns a dict definings fits for numerical features
    A fit is an ordered list of tuples defining each bin's range

    Returned dict allows for fitting to training data and applying the same fit to test data
    to avoid information leak.
    """

    def bin_fit_feat(df, feat, n_bins=10):
        """
        Returns list of tuples defining bin ranges for a numerical feature
        """
        n_bins = min(
            n_bins, len(df[feat].unique())
        )  # In case there are fewer unique values than n_bins
        bin_size = len(df) // n_bins
        sorted_df = df.sort_values(by=[feat])
        sorted_values = sorted_df[feat].tolist()

        if verbosity >= 4:
            print(
                f"{feat}: fitting {len(df[feat].unique())} unique vals into {n_bins} bins"
            )
        bin_ranges = []
        finish_i = -1
        sizes = []

        bin = 0
        start_i = 0
        while bin < n_bins and start_i < len(sorted_values):
            finish_i = min(start_i + bin_size, len(sorted_df) - 1)
            while (
                finish_i < len(sorted_df) - 1
                and finish_i != 0
                and sorted_df.iloc[finish_i][feat] == sorted_df.iloc[finish_i - 1][feat]
            ):  # ensure next bin begins on a new value
                finish_i += 1
            sizes.append(finish_i - start_i)
            if verbosity >= 4:
                print(
                    f"bin #{bin}, start_idx {start_i} value: {sorted_df.iloc[start_i][feat]}, finish_idxx {finish_i} value: {sorted_df.iloc[finish_i][feat]}"
                )
            start_val = sorted_values[start_i]
            finish_val = sorted_values[finish_i]
            bin_range = (start_val, finish_val)
            bin_ranges.append(bin_range)

            start_i = finish_i + 1
            bin += 1

        if verbosity >= 4:
            print(
                f"-bin sizes {sizes}; dataVMR={rnd(var(df[feat])/mean(df[feat]))}, binVMR={rnd(var(sizes)/mean(sizes))}"
            )  # , axis=None, dtype=None, out=None, ddof=0)})
        return bin_ranges

    # Create dict to store fit definitions for each feature
    fit_dict = {}
    feats_to_fit = find_numeric_feats(df, ignore_feats=ignore_feats)
    if verbosity == 2:
        print(f"fitting bins for features {feats_to_fit}")
    if verbosity >= 2:
        print()

    # Collect fits in dict
    count = 1
    for feat in feats_to_fit:
        fit = bin_fit_feat(df, feat, n_bins=n_bins)
        fit_dict[feat] = fit
    return fit_dict


def bin_transform(df, fit_dict, names_precision=2):
    """
    Uses a pre-collected dictionary of fits to transform df features into bins.
    Returns the fit df rather than modifying inplace.
    """

    def bin_transform_feat(df, feat, bin_fits, names_precision=names_precision):
        """
        Returns new dataframe with n_bin bins replacing each numerical feature
        """

        def renamed(bin_fit_list, value, names_precision=names_precision):
            """
            Returns bin string name for a given numberical value
            Assumes bin_fit_list is ordered
            """
            min_val, min_bin = bin_fit_list[0][0], bin_fit_list[0]
            max_val, max_bin = bin_fit_list[-1][1], bin_fit_list[-1]
            for bin_fit in bin_fits:
                if value <= bin_fit[1]:
                    start_name = str(round(bin_fit[0], names_precision))
                    finish_name = str(round(bin_fit[1], names_precision))
                    bin_name = "-".join([start_name, finish_name])
                    return bin_name
            if value <= min_val:
                return min_bin
            elif value >= max_val:
                return max_bin
            else:
                raise ValueError("No bin found for value", value)

        renamed_values = []
        for value in df[feat]:
            bin_name = renamed(bin_fits, value, names_precision)
            renamed_values.append(bin_name)
        return renamed_values

    # Replace each feature with bin transformations
    for feat, bin_fits in fit_dict.items():
        if feat in df.columns:
            feat_transformation = bin_transform_feat(
                df, feat, bin_fits, names_precision=names_precision
            )
            df[feat] = feat_transformation
    return df



def _try_rename_features(df, class_feat, feature_names):
    """ Rename df columns according to user request. """
    # Rename if same number of features
    df_columns = [col for col in df.columns.tolist() if col != class_feat]
    if len(df_columns) == len(feature_names):
        col_replacements_dict = {
            old: new for old, new in zip(df_columns, feature_names)
        }
        df = df.rename(columns=col_replacements_dict)
        return df
    # Wrong number of feature names
    else:
        return None